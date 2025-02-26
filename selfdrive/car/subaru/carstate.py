import copy
from cereal import car
from opendbc.can.can_define import CANDefine
from common.conversions import Conversions as CV
from selfdrive.car.interfaces import CarStateBase
from opendbc.can.parser import CANParser
from selfdrive.car.subaru.values import DBC, STEER_THRESHOLD, CAR, PREGLOBAL_CARS
from common.params import Params


class CarState(CarStateBase):
  def __init__(self, CP):
    super().__init__(CP)
    can_define = CANDefine(DBC[CP.carFingerprint]["pt"])
    self.shifter_values = can_define.dv["Transmission"]["Gear"]

    params = Params()
    self.has_epb = params.get("ManualParkingBrakeSNGToggle", encoding='utf8') == "0"

  def update(self, cp, cp_cam, cp_body):
    ret = car.CarState.new_message()

    if self.car_fingerprint == CAR.CROSSTREK_2020H:
      ret.gas = cp_body.vl["Throttle_Hybrid"]["Throttle_Pedal"] / 255.
    else:
      ret.gas = cp.vl["Throttle"]["Throttle_Pedal"] / 255.
    ret.gasPressed = ret.gas > 1e-5
    if self.car_fingerprint in PREGLOBAL_CARS:
      ret.brakePressed = cp.vl["Brake_Pedal"]["Brake_Pedal"] > 2
    elif self.car_fingerprint in [CAR.OUTBACK, CAR.LEGACY]:
      ret.brakePressed = cp_body.vl["Brake_Status"]["Brake"] == 1
    elif self.car_fingerprint == CAR.CROSSTREK_2020H:
      ret.brakePressed = cp_body.vl["Brake_Hybrid"]["Brake"] == 1
    else:
      ret.brakePressed = cp.vl["Brake_Status"]["Brake"] == 1

    if self.car_fingerprint in [CAR.OUTBACK, CAR.LEGACY]:
      ret.wheelSpeeds = self.get_wheel_speeds(
        cp_body.vl["Wheel_Speeds"]["FL"],
        cp_body.vl["Wheel_Speeds"]["FR"],
        cp_body.vl["Wheel_Speeds"]["RL"],
        cp_body.vl["Wheel_Speeds"]["RR"],
      )
    else:
      ret.wheelSpeeds = self.get_wheel_speeds(
        cp.vl["Wheel_Speeds"]["FL"],
        cp.vl["Wheel_Speeds"]["FR"],
        cp.vl["Wheel_Speeds"]["RL"],
        cp.vl["Wheel_Speeds"]["RR"],
      )
    ret.vEgoRaw = (ret.wheelSpeeds.fl + ret.wheelSpeeds.fr + ret.wheelSpeeds.rl + ret.wheelSpeeds.rr) / 4.
    # Kalman filter, even though Subaru raw wheel speed is heaviliy filtered by default
    ret.vEgo, ret.aEgo = self.update_speed_kf(ret.vEgoRaw)
    ret.standstill = ret.vEgoRaw < 0.01

    # continuous blinker signals for assisted lane change
    ret.leftBlinker, ret.rightBlinker = self.update_blinker_from_lamp(
      50, cp.vl["Dashlights"]["LEFT_BLINKER"], cp.vl["Dashlights"]["RIGHT_BLINKER"])

    if self.CP.enableBsm:
      ret.leftBlindspot = (cp.vl["BSD_RCTA"]["L_ADJACENT"] == 1) or (cp.vl["BSD_RCTA"]["L_APPROACHING"] == 1)
      ret.rightBlindspot = (cp.vl["BSD_RCTA"]["R_ADJACENT"] == 1) or (cp.vl["BSD_RCTA"]["R_APPROACHING"] == 1)

    if self.car_fingerprint == CAR.CROSSTREK_2020H:
      can_gear = int(cp_body.vl["Transmission"]["Gear"])
    else:
      can_gear = int(cp.vl["Transmission"]["Gear"])
    ret.gearShifter = self.parse_gear_shifter(self.shifter_values.get(can_gear, None))

    if self.car_fingerprint == CAR.WRX_PREGLOBAL:
      ret.steeringAngleDeg = cp.vl["Steering"]["Steering_Angle"]
    else:
      ret.steeringAngleDeg = cp.vl["Steering_Torque"]["Steering_Angle"]
    ret.steeringTorque = cp.vl["Steering_Torque"]["Steer_Torque_Sensor"]
    ret.steeringPressed = abs(ret.steeringTorque) > STEER_THRESHOLD[self.car_fingerprint]

    if self.car_fingerprint in [CAR.OUTBACK, CAR.LEGACY]:
      ret.cruiseState.enabled = cp_body.vl["CruiseControl"]["Cruise_Activated"] != 0
      ret.cruiseState.available = cp_body.vl["CruiseControl"]["Cruise_On"] != 0
    elif self.car_fingerprint in [CAR.CROSSTREK_2020H, CAR.FORESTER_2020H]:
      ret.cruiseState.enabled = cp_cam.vl["ES_DashStatus"]['Cruise_Activated'] != 0
      ret.cruiseState.available = cp_cam.vl["ES_DashStatus"]['Cruise_On'] != 0
    else:
      ret.cruiseState.enabled = cp.vl["CruiseControl"]["Cruise_Activated"] != 0
      ret.cruiseState.available = cp.vl["CruiseControl"]["Cruise_On"] != 0
    ret.cruiseState.speed = cp_cam.vl["ES_DashStatus"]["Cruise_Set_Speed"] * CV.KPH_TO_MS

    if (self.car_fingerprint in PREGLOBAL_CARS and cp.vl["Dash_State2"]["UNITS"] == 1) or \
       (self.car_fingerprint not in PREGLOBAL_CARS and cp.vl["Dashlights"]["UNITS"] == 1):
      ret.cruiseState.speed *= CV.MPH_TO_KPH

    ret.seatbeltUnlatched = cp.vl["Dashlights"]["SEATBELT_FL"] == 1
    ret.doorOpen = any([cp.vl["BodyInfo"]["DOOR_OPEN_RR"],
                        cp.vl["BodyInfo"]["DOOR_OPEN_RL"],
                        cp.vl["BodyInfo"]["DOOR_OPEN_FR"],
                        cp.vl["BodyInfo"]["DOOR_OPEN_FL"]])
    ret.steerFaultPermanent = cp.vl["Steering_Torque"]["Steer_Error_1"] == 1
    self.throttle_msg = copy.copy(cp.vl["Throttle"])

    if self.car_fingerprint in PREGLOBAL_CARS:
      self.cruise_button = cp_cam.vl["ES_Distance"]["Cruise_Button"]
      self.ready = not cp_cam.vl["ES_DashStatus"]["Not_Ready_Startup"]
      self.es_distance_msg = copy.copy(cp_cam.vl["ES_Distance"])
      self.car_follow = cp_cam.vl["ES_Distance"]["Car_Follow"]
      self.close_distance = cp_cam.vl["ES_Distance"]["Close_Distance"]
    else:
      ret.steerFaultTemporary = cp.vl["Steering_Torque"]["Steer_Warning"] == 1
      ret.cruiseState.nonAdaptive = cp_cam.vl["ES_DashStatus"]["Conventional_Cruise"] == 1
      self.cruise_state = cp_cam.vl["ES_DashStatus"]["Cruise_State"]
      self.brake_pedal_msg = copy.copy(cp.vl["Brake_Pedal"])
      self.es_lkas_msg = copy.copy(cp_cam.vl["ES_LKAS_State"])
      if self.car_fingerprint in [CAR.OUTBACK, CAR.LEGACY]:
        self.car_follow = cp_body.vl["ES_Distance"]["Car_Follow"]
        self.close_distance = cp_body.vl["ES_Distance"]["Close_Distance"]
      # FIXME: find ES_Distance signals for CROSSTREK_2020H
      elif self.car_fingerprint != CAR.CROSSTREK_2020H:
        self.car_follow = cp_cam.vl["ES_Distance"]["Car_Follow"]
        self.close_distance = cp_cam.vl["ES_Distance"]["Close_Distance"]
        self.es_distance_msg = copy.copy(cp_cam.vl["ES_Distance"])
      self.es_dashstatus_msg = copy.copy(cp_cam.vl["ES_DashStatus"])

    return ret

  @staticmethod
  def get_can_parser(CP):
    signals = [
      # sig_name, sig_address
      ("Steer_Torque_Sensor", "Steering_Torque"),
      ("Steering_Angle", "Steering_Torque"),
      ("Steer_Error_1", "Steering_Torque"),
      ("Brake_Pedal", "Brake_Pedal"),
      ("LEFT_BLINKER", "Dashlights"),
      ("RIGHT_BLINKER", "Dashlights"),
      ("SEATBELT_FL", "Dashlights"),
      ("DOOR_OPEN_FR", "BodyInfo"),
      ("DOOR_OPEN_FL", "BodyInfo"),
      ("DOOR_OPEN_RR", "BodyInfo"),
      ("DOOR_OPEN_RL", "BodyInfo"),
    ]
    checks = [
      # sig_address, frequency
      ("Throttle", 100),
      ("Brake_Pedal", 50),
      ("Steering_Torque", 50),
    ]

    # Wheel_Speeds is on can1 for OUTBACK
    if CP.carFingerprint not in [CAR.OUTBACK, CAR.LEGACY]:
      signals += [
        ("FL", "Wheel_Speeds"),
        ("FR", "Wheel_Speeds"),
        ("RL", "Wheel_Speeds"),
        ("RR", "Wheel_Speeds"),
      ]
      checks.append(("Wheel_Speeds", 50))

    # Transmission is on can1 for CROSSTREK_2020H
    if CP.carFingerprint != CAR.CROSSTREK_2020H:
      signals.append(("Gear", "Transmission"))
      checks.append(("Transmission", 100))

    # CruiseControl is on can1 for OUTBACK and not used for CROSSTREK_2020H
    if CP.carFingerprint not in [CAR.OUTBACK, CAR.LEGACY, CAR.CROSSTREK_2020H]:
      signals.append(("Cruise_On", "CruiseControl"))
      signals.append(("Cruise_Activated", "CruiseControl"))

    if CP.carFingerprint in PREGLOBAL_CARS:
      signals += [
        ("Throttle_Pedal", "Throttle"),
        ("Counter", "Throttle"),
        ("Signal1", "Throttle"),
        ("Not_Full_Throttle", "Throttle"),
        ("Signal2", "Throttle"),
        ("Engine_RPM", "Throttle"),
        ("Off_Throttle", "Throttle"),
        ("Signal3", "Throttle"),
        ("Throttle_Cruise", "Throttle"),
        ("Throttle_Combo", "Throttle"),
        ("Throttle_Body", "Throttle"),
        ("Off_Throttle_2", "Throttle"),
        ("Signal4", "Throttle"),

        ("UNITS", "Dash_State2"),
        ("Steering_Angle", "Steering"),
      ]

      checks.append(("BodyInfo", 1))
      checks.append(("CruiseControl", 50))
      checks.append(("Dash_State2", 1))
      checks.append(("Steering", 50))

      if CP.carFingerprint in [CAR.FORESTER_PREGLOBAL, CAR.LEVORG_PREGLOBAL, CAR.WRX_PREGLOBAL]:
        checks.append(("Dashlights", 20))
      elif CP.carFingerprint in [CAR.LEGACY_PREGLOBAL, CAR.LEGACY_PREGLOBAL_2018, CAR.OUTBACK_PREGLOBAL, CAR.OUTBACK_PREGLOBAL_2018]:
        checks.append(("Dashlights", 10))

    else:
      signals += [
        ("Counter", "Throttle"),
        ("Signal1", "Throttle"),
        ("Engine_RPM", "Throttle"),
        ("Signal2", "Throttle"),
        ("Throttle_Pedal", "Throttle"),
        ("Throttle_Cruise", "Throttle"),
        ("Throttle_Combo", "Throttle"),
        ("Signal1", "Throttle"),
        ("Off_Accel", "Throttle"),

        ("Counter", "Brake_Pedal"),
        ("Signal1", "Brake_Pedal"),
        ("Speed", "Brake_Pedal"),
        ("Signal2", "Brake_Pedal"),
        ("Brake_Lights", "Brake_Pedal"),
        ("Signal3", "Brake_Pedal"),
        ("Signal4", "Brake_Pedal"),

        ("Steer_Warning", "Steering_Torque"),
        ("UNITS", "Dashlights"),
      ]
      checks.append(("Dashlights", 10))
      checks.append(("BodyInfo", 10))

      # Brake_Status is on can1 for OUTBACK
      if CP.carFingerprint not in [CAR.OUTBACK, CAR.LEGACY]:
        signals.append(("Brake", "Brake_Status"))
        checks.append(("Brake_Status", 50))

      # CruiseControl is on can1 for OUTBACK and nod used for CROSSTREK_2020H
      if CP.carFingerprint not in [CAR.OUTBACK, CAR.LEGACY, CAR.CROSSTREK_2020H]:
        checks.append(("CruiseControl", 20))

    if CP.enableBsm:
      signals += [
        ("L_ADJACENT", "BSD_RCTA"),
        ("R_ADJACENT", "BSD_RCTA"),
        ("L_APPROACHING", "BSD_RCTA"),
        ("R_APPROACHING", "BSD_RCTA"),
      ]
      checks.append(("BSD_RCTA", 17))

    return CANParser(DBC[CP.carFingerprint]["pt"], signals, checks, 0)

  @staticmethod
  def get_body_can_parser(CP):
    signals = []
    checks = []

    if CP.carFingerprint == CAR.CROSSTREK_2020H:
      signals += [
        ("Throttle_Pedal", "Throttle_Hybrid"),
        ("Brake", "Brake_Hybrid"),
        ("Gear", "Transmission"),
      ]

      checks.append(("Throttle_Hybrid", 50))
      checks.append(("Brake_Hybrid", 40))
      checks.append(("Transmission", 50))

      return CANParser(DBC[CP.carFingerprint]['pt'], signals, checks, 1)

    elif CP.carFingerprint in [CAR.OUTBACK, CAR.LEGACY]:
      signals += [
        ("Cruise_On", "CruiseControl"),
        ("Cruise_Activated", "CruiseControl"),
        ("FL", "Wheel_Speeds"),
        ("FR", "Wheel_Speeds"),
        ("RL", "Wheel_Speeds"),
        ("RR", "Wheel_Speeds"),
        ("Brake", "Brake_Status"),
        ("Car_Follow", "ES_Distance"),
        ("Close_Distance", "ES_Distance"),
      ]

      checks.append(("CruiseControl", 20))
      checks.append(("ES_Distance", 20))
      checks.append(("Wheel_Speeds", 50))
      checks.append(("Brake_Status", 50))

      return CANParser(DBC[CP.carFingerprint]["pt"], signals, checks, 1)

    else:
      return None

  @staticmethod
  def get_cam_can_parser(CP):
    if CP.carFingerprint in PREGLOBAL_CARS:
      signals = [
        ("Cruise_Set_Speed", "ES_DashStatus"),
        ("Not_Ready_Startup", "ES_DashStatus"),
        ("Car_Follow", "ES_DashStatus"),

        ("Cruise_Throttle", "ES_Distance"),
        ("Signal1", "ES_Distance"),
        ("Car_Follow", "ES_Distance"),
        ("Signal2", "ES_Distance"),
        ("Brake_On", "ES_Distance"),
        ("Distance_Swap", "ES_Distance"),
        ("Standstill", "ES_Distance"),
        ("Signal3", "ES_Distance"),
        ("Close_Distance", "ES_Distance"),
        ("Signal4", "ES_Distance"),
        ("Standstill_2", "ES_Distance"),
        ("Cruise_Fault", "ES_Distance"),
        ("Signal5", "ES_Distance"),
        ("Counter", "ES_Distance"),
        ("Signal6", "ES_Distance"),
        ("Cruise_Button", "ES_Distance"),
        ("Signal7", "ES_Distance"),
      ]
      checks = [
        ("ES_DashStatus", 20),
        ("ES_Distance", 20),
      ]

    else:
      signals = [
        ("Counter", "ES_DashStatus"),
        ("PCB_Off", "ES_DashStatus"),
        ("LDW_Off", "ES_DashStatus"),
        ("Signal1", "ES_DashStatus"),
        ("Cruise_State_Msg", "ES_DashStatus"),
        ("LKAS_State_Msg", "ES_DashStatus"),
        ("Signal2", "ES_DashStatus"),
        ("Cruise_Soft_Disable", "ES_DashStatus"),
        ("EyeSight_Status_Msg", "ES_DashStatus"),
        ("Signal3", "ES_DashStatus"),
        ("Cruise_Distance", "ES_DashStatus"),
        ("Signal4", "ES_DashStatus"),
        ("Conventional_Cruise", "ES_DashStatus"),
        ("Signal5", "ES_DashStatus"),
        ("Cruise_Disengaged", "ES_DashStatus"),
        ("Cruise_Activated", "ES_DashStatus"),
        ("Signal6", "ES_DashStatus"),
        ("Cruise_Set_Speed", "ES_DashStatus"),
        ("Cruise_Fault", "ES_DashStatus"),
        ("Cruise_On", "ES_DashStatus"),
        ("Display_Own_Car", "ES_DashStatus"),
        ("Brake_Lights", "ES_DashStatus"),
        ("Car_Follow", "ES_DashStatus"),
        ("Signal7", "ES_DashStatus"),
        ("Far_Distance", "ES_DashStatus"),
        ("Cruise_State", "ES_DashStatus"),

        ("Counter", "ES_LKAS_State"),
        ("LKAS_Alert_Msg", "ES_LKAS_State"),
        ("Signal1", "ES_LKAS_State"),
        ("LKAS_ACTIVE", "ES_LKAS_State"),
        ("LKAS_Dash_State", "ES_LKAS_State"),
        ("Signal2", "ES_LKAS_State"),
        ("Backward_Speed_Limit_Menu", "ES_LKAS_State"),
        ("LKAS_Left_Line_Enable", "ES_LKAS_State"),
        ("LKAS_Left_Line_Light_Blink", "ES_LKAS_State"),
        ("LKAS_Right_Line_Enable", "ES_LKAS_State"),
        ("LKAS_Right_Line_Light_Blink", "ES_LKAS_State"),
        ("LKAS_Left_Line_Visible", "ES_LKAS_State"),
        ("LKAS_Right_Line_Visible", "ES_LKAS_State"),
        ("LKAS_Alert", "ES_LKAS_State"),
        ("Signal3", "ES_LKAS_State"),
      ]
      checks = [
        ("ES_DashStatus", 10),
        ("ES_LKAS_State", 10),
      ]

      if CP.carFingerprint not in [CAR.CROSSTREK_2020H, CAR.OUTBACK, CAR.LEGACY]:
        signals += [
          ("Counter", "ES_Distance"),
          ("Signal1", "ES_Distance"),
          ("Cruise_Fault", "ES_Distance"),
          ("Cruise_Throttle", "ES_Distance"),
          ("Signal2", "ES_Distance"),
          ("Car_Follow", "ES_Distance"),
          ("Signal3", "ES_Distance"),
          ("Cruise_Brake_Active", "ES_Distance"),
          ("Distance_Swap", "ES_Distance"),
          ("Cruise_EPB", "ES_Distance"),
          ("Signal4", "ES_Distance"),
          ("Close_Distance", "ES_Distance"),
          ("Signal5", "ES_Distance"),
          ("Cruise_Cancel", "ES_Distance"),
          ("Cruise_Set", "ES_Distance"),
          ("Cruise_Resume", "ES_Distance"),
          ("Signal6", "ES_Distance"),
        ]
        checks.append(("ES_Distance", 20))

    return CANParser(DBC[CP.carFingerprint]["pt"], signals, checks, 2)
