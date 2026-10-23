from unittest.mock import MagicMock
import numpy as np
from opendbc.car.structs import CarParams
from openpilot.cereal import custom, log
from openpilot.common.test import OpenpilotTestCase
from openpilot.selfdrive.modeld.constants import ModelConstants
from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import T_IDXS as T_IDXS_MPC
from openpilot.selfdrive.controls.lib.drive_helpers import get_accel_from_plan
from openpilot.selfdrive.controls.lib.longitudinal_planner import (
  LongitudinalPlanner,
  LAUNCH_DISARM_SPEED,
  LAUNCH_COMMIT_T,
  LAUNCH_MOVING_SPEED,
  LAUNCH_MAX_ACCEL,
)


def create_mock_submaster(v_ego=0.0, standstill=True, experimental_mode=True, should_stop=False,
                          velocity_x=None, acceleration_x=None, desired_accel=0.1):
  if velocity_x is None:
    velocity_x = list(np.linspace(0.0, 10.0, ModelConstants.IDX_N))
  if acceleration_x is None:
    acceleration_x = list(np.ones(ModelConstants.IDX_N) * 1.5)

  mock_dict = {
    'carControl': MagicMock(orientationNED=[], cruiseControl=MagicMock(override=False)),
    'carState': MagicMock(vEgo=v_ego, vCruise=30.0, vCruiseCluster=30.0, standstill=standstill,
                          gasPressed=False, steeringAngleDeg=0.0, aEgo=0.0),
    'carStateSP': custom.CarStateSP.new_message(),
    'controlsState': MagicMock(longControlState=1, forceDecel=False),
    'controlsStateSP': MagicMock(),
    'selfdriveState': MagicMock(enabled=True, personality=log.LongitudinalPersonality.standard,
                                experimentalMode=experimental_mode),
    'selfdriveStateSP': custom.SelfdriveStateSP.new_message(),
    'vehicleParameters': MagicMock(angleOffsetDeg=0.0),
    'radarState': MagicMock(leadOne=MagicMock(present=False), leadTwo=MagicMock(present=False)),
    'modelV2': MagicMock(
      meta=MagicMock(disengagePredictions=MagicMock(gasPressProbs=[0.0, 1.0])),
      action=MagicMock(desiredAcceleration=desired_accel, shouldStop=should_stop),
      velocity=MagicMock(x=velocity_x),
      acceleration=MagicMock(x=acceleration_x),
      orientationRate=MagicMock(z=list(np.ones(ModelConstants.IDX_N) * 0.01)),
    ),
    'liveMapDataSP': MagicMock(speedLimitValid=False, speedLimitAheadValid=False),
  }

  sm = MagicMock()
  sm.__getitem__.side_effect = lambda k: mock_dict.get(k, MagicMock(unixTimestampMillis=0.0))
  sm.data = mock_dict
  sm.__contains__.side_effect = lambda k: k in mock_dict
  return sm


class TestGreenLightLaunch(OpenpilotTestCase):
  def setUp(self):
    CP = CarParams()
    CP.openpilotLongitudinalControl = True
    CP.steerRatio = 15.0
    CP.wheelbase = 2.7
    CP.longitudinalActuatorDelay = 0.2
    CP_SP = custom.CarParamsSP.new_message()
    self.planner = LongitudinalPlanner(CP, CP_SP)
    self.planner.scc.vision.enabled = False
    self.planner.a_cruise = 1.6

  def test_arming_and_disarming(self):
    assert not self.planner.launch_armed

    # Standstill arms launch
    sm_stopped = create_mock_submaster(v_ego=0.0, standstill=True)
    self.planner.update(sm_stopped)
    assert self.planner.launch_armed

    # Remains armed when moving below LAUNCH_DISARM_SPEED
    sm_moving_slow = create_mock_submaster(v_ego=1.0, standstill=False)
    self.planner.update(sm_moving_slow)
    assert self.planner.launch_armed

    # Disarms when exceeding LAUNCH_DISARM_SPEED
    sm_moving_fast = create_mock_submaster(v_ego=LAUNCH_DISARM_SPEED + 0.5, standstill=False)
    self.planner.update(sm_moving_fast)
    assert not self.planner.launch_armed

  def test_launch_acceleration_math(self):
    # Verify expected launch acceleration calculation
    v_ego = 0.0
    action_t = 0.2 + 0.05
    raw_desired_accel = 0.1

    vel_x = np.linspace(0.0, 10.0, ModelConstants.IDX_N)
    acc_x = np.ones(ModelConstants.IDX_N) * 1.5

    model_v = np.interp(T_IDXS_MPC, ModelConstants.T_IDXS, vel_x)
    model_a = np.interp(T_IDXS_MPC, ModelConstants.T_IDXS, acc_x)

    assert np.interp(LAUNCH_COMMIT_T, T_IDXS_MPC, model_v) > LAUNCH_DISARM_SPEED

    t_cut = min(float(T_IDXS_MPC[np.argmax(model_v > LAUNCH_MOVING_SPEED)]), LAUNCH_COMMIT_T)
    t_shifted = T_IDXS_MPC + t_cut
    v_shifted = np.interp(t_shifted, T_IDXS_MPC, model_v)
    a_shifted = np.interp(t_shifted, T_IDXS_MPC, model_a)
    a_launch = get_accel_from_plan(v_shifted, a_shifted, T_IDXS_MPC, action_t=action_t)
    a_launch_max = np.interp(v_ego, [LAUNCH_MOVING_SPEED, LAUNCH_DISARM_SPEED], [LAUNCH_MAX_ACCEL, 0.])

    boosted_a = max(raw_desired_accel, min(a_launch, a_launch_max))
    assert boosted_a == LAUNCH_MAX_ACCEL  # At v_ego=0, a_launch_max is 1.5 m/s^2

  def test_green_light_launch_triggers_and_clears_should_stop(self):
    # Vehicle stopped at a red light that just turned green:
    # Model action still says shouldStop=True (creep / negative accel), but future trajectory commits!
    self.planner.launch_armed = True
    vel_x = list(np.linspace(0.0, 10.0, ModelConstants.IDX_N))
    acc_x = list(np.ones(ModelConstants.IDX_N) * 1.5)

    sm = create_mock_submaster(v_ego=0.0, standstill=True, experimental_mode=True,
                               should_stop=True, velocity_x=vel_x, acceleration_x=acc_x, desired_accel=-0.09)
    self.planner.update(sm)

    # Launch should trigger, boosting aTarget and clearing output_should_stop
    assert not self.planner.output_should_stop
    assert self.planner.output_a_target >= LAUNCH_MAX_ACCEL

  def test_green_light_launch_not_triggered_when_no_commit(self):
    self.planner.launch_armed = True
    # Model predicts 0 velocity across the board (red light, not moving)
    vel_x = [0.001] * ModelConstants.IDX_N
    acc_x = [0.0] * ModelConstants.IDX_N

    sm = create_mock_submaster(v_ego=0.0, standstill=True, experimental_mode=True,
                               should_stop=True, velocity_x=vel_x, acceleration_x=acc_x, desired_accel=-0.10)
    self.planner.update(sm)

    # Launch should NOT trigger; car should remain stopped
    assert self.planner.output_should_stop
    assert self.planner.launch_armed

  def test_green_light_launch_not_triggered_when_not_armed(self):
    self.planner.launch_armed = False
    vel_x = list(np.linspace(0.0, 10.0, ModelConstants.IDX_N))
    acc_x = list(np.ones(ModelConstants.IDX_N) * 1.5)

    # Moving above disarm speed
    sm = create_mock_submaster(v_ego=LAUNCH_DISARM_SPEED + 1.0, standstill=False,
                               should_stop=False, velocity_x=vel_x, acceleration_x=acc_x, desired_accel=0.5)
    self.planner.update(sm)
    assert not self.planner.launch_armed
