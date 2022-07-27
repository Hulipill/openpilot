from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Union

from selfdrive.car import dbc_dict
from selfdrive.car.docs_definitions import CarInfo, Harness
from cereal import car

Ecu = car.CarParams.Ecu


class CarControllerParams:
  def __init__(self, CP):
    if CP.carFingerprint == CAR.IMPREZA_2020:
      self.STEER_MAX = 1439
    elif CP.carFingerprint == CAR.FORESTER_PREGLOBAL:
      self.STEER_MAX = 3071
    elif CP.carFingerprint == CAR.OUTBACK_PREGLOBAL_2018:
      self.STEER_MAX = 3071
    else:
      self.STEER_MAX = 2047
    self.STEER_STEP = 2                # how often we update the steer cmd
    self.STEER_DELTA_UP = 50           # torque increase per refresh, 0.8s to max
    self.STEER_DELTA_DOWN = 70         # torque decrease per refresh
    self.STEER_DRIVER_ALLOWANCE = 60   # allowed driver torque before start limiting
    self.STEER_DRIVER_MULTIPLIER = 10  # weight driver torque heavily
    self.STEER_DRIVER_FACTOR = 1       # from dbc
    self.ACC_MIN_DIST = 3              # stop and go min distance threshold
    self.ACC_MAX_DIST = 4.5            # stop and go max distance threshold


class CAR:
  ASCENT = "SUBARU ASCENT LIMITED 2019"
  IMPREZA = "SUBARU IMPREZA LIMITED 2019"
  IMPREZA_2020 = "SUBARU IMPREZA SPORT 2020"
  CROSSTREK_2020H = "SUBARU CROSSTREK LIMITED 2020 HYBRID"
  FORESTER = "SUBARU FORESTER 2019"
  FORESTER_2020H = "SUBARU FORESTER 2020 HYBRID"
  FORESTER_PREGLOBAL = "SUBARU FORESTER 2017 - 2018"
  LEGACY = "SUBARU LEGACY 2020"
  LEGACY_PREGLOBAL = "SUBARU LEGACY 2015 - 2017"
  LEGACY_PREGLOBAL_2018 = "SUBARU LEGACY 2018 - 2019"
  LEVORG_PREGLOBAL = "SUBARU LEVORG 2016"
  OUTBACK = "SUBARU OUTBACK 2020"
  OUTBACK_PREGLOBAL = "SUBARU OUTBACK 2015 - 2017"
  OUTBACK_PREGLOBAL_2018 = "SUBARU OUTBACK 2018 - 2019"
  WRX_PREGLOBAL = "SUBARU WRX 2018"


@dataclass
class SubaruCarInfo(CarInfo):
  package: str = "EyeSight"
  harness: Enum = Harness.subaru


CAR_INFO: Dict[str, Union[SubaruCarInfo, List[SubaruCarInfo]]] = {
  CAR.ASCENT: SubaruCarInfo("Subaru Ascent 2019-21", "All"),
  CAR.IMPREZA: [
    SubaruCarInfo("Subaru Impreza 2017-19"),
    SubaruCarInfo("Subaru Crosstrek 2018-19", video_link="https://youtu.be/Agww7oE1k-s?t=26"),
    SubaruCarInfo("Subaru XV 2018-19", video_link="https://youtu.be/Agww7oE1k-s?t=26"),
  ],
  CAR.IMPREZA_2020: [
    SubaruCarInfo("Subaru Impreza 2020-22"),
    SubaruCarInfo("Subaru Crosstrek 2020-21"),
    SubaruCarInfo("Subaru XV 2020-21"),
  ],
  CAR.CROSSTREK_2020H: SubaruCarInfo("Subaru Crosstrek Hybrid 2020"),
  CAR.FORESTER: SubaruCarInfo("Subaru Forester 2019-22", "All"),
  CAR.FORESTER_2020H: SubaruCarInfo("Subaru Forester Hybrid 2020"),
  CAR.FORESTER_PREGLOBAL: SubaruCarInfo("Subaru Forester 2017-18"),
  CAR.LEGACY: SubaruCarInfo("Subaru Legacy 2020"),
  CAR.LEGACY_PREGLOBAL: SubaruCarInfo("Subaru Legacy 2015-17"),
  CAR.LEGACY_PREGLOBAL_2018: SubaruCarInfo("Subaru Legacy 2018-19"),
  CAR.LEVORG_PREGLOBAL: SubaruCarInfo("Subaru Levorg 2016"),
  CAR.OUTBACK: SubaruCarInfo("Subaru Outback 2020"),
  CAR.OUTBACK_PREGLOBAL: SubaruCarInfo("Subaru Outback 2015-17"),
  CAR.OUTBACK_PREGLOBAL_2018: SubaruCarInfo("Subaru Outback 2018-19"),
  CAR.WRX_PREGLOBAL: SubaruCarInfo("Subaru WRX 2016-18"),
}


FW_VERSIONS = {
  CAR.ASCENT: {
    (Ecu.esp, 0x7b0, None): [
      b'\x00 \x00\x00\x00',
    ],
    (Ecu.eps, 0x746, None): [
      b'\x00\x00\x00\x00',
    ],
    (Ecu.fwdCamera, 0x787, None): [
      b'\x00\x00\x00\x00 \x00',
    ],
    (Ecu.engine, 0x7e0, None): [
      b'\x00,\x00\a',
    ],
    (Ecu.transmission, 0x7e1, None): [
      b'\x00\x00\x00\x00\x00',
    ],
  },
  CAR.IMPREZA: {
    (Ecu.esp, 0x7b0, None): [
      b'\x00\x00\x00\x00\x00',
    ],
    (Ecu.eps, 0x746, None): [
      b'\x00\x00\x00\x00',
    ],
    (Ecu.fwdCamera, 0x787, None): [
      b'\000\000\000\000\000\000',
    ],
    (Ecu.engine, 0x7e0, None): [
      b'\x00\x00',
    ],
    (Ecu.transmission, 0x7e1, None): [
      b'\x00\x00\x00',
    ],
  },
  CAR.IMPREZA_2020: {
    (Ecu.esp, 0x7b0, None): [
      b'\x00\000',
    ],
    (Ecu.eps, 0x746, None): [
      b'\x00\x00\x00\x00',
    ],
    (Ecu.fwdCamera, 0x787, None): [
      b'\000\000\000',
    ],
    (Ecu.engine, 0x7e0, None): [
      b'\x000\0',
    ],
    (Ecu.transmission, 0x7e1, None): [
      b'\x000\x000\000\000\000',
    ],
  },
  CAR.CROSSTREK_2020H: {
    # 2020 Crosstrek Hybrid - UDM / @revity
    # 2020 Crosstrek Hybrid - UDM / @Dave32
    # Ecu, addr, subaddr: ROM ID
    (Ecu.esp, 0x7b0, None): [
      b'\x00 \x000\x00',
    ],
    (Ecu.eps, 0x746, None): [
      b'\x00\x00\x00\x00',
    ],
    (Ecu.fwdCamera, 0x787, None): [
      b'\x00\x000\x000',
    ],
    (Ecu.engine, 0x7e0, None): [
      b'\x000\x000',
    ],
  },
  CAR.FORESTER: {
    (Ecu.esp, 0x7b0, None): [
      b'\xa3 \x00\x00\x00',
    ],
    (Ecu.eps, 0x746, None): [
      b'\x00\x00\x00\x00',
    ],
    (Ecu.fwdCamera, 0x787, None): [
      b'\x00\x00',
    ],
    (Ecu.engine, 0x7e0, None): [
      b'\x00\x00',
    ],
    (Ecu.transmission, 0x7e1, None): [
      b'\000\x00\000',
    ],
  },
  CAR.FORESTER_2020H: {
    (Ecu.esp, 0x7b0, None): [
      b'\x000\x00\x00',
    ],
    (Ecu.eps, 0x746, None): [
      b'\x00\x00\x00\x00',
    ],
    (Ecu.fwdCamera, 0x787, None): [
      b'\x00\x00\x00',
    ],
    (Ecu.engine, 0x7e0, None): [
      b'\x00\x00\x00',
    ],
    (Ecu.transmission, 0x7e1, None): [
      b'\x00\x00\x00',
    ],
  },
  CAR.FORESTER_PREGLOBAL: {
    (Ecu.esp, 0x7b0, None): [
      b'\x7d\x97\x14\x40',
      b'\xf1\x00\xbb\x0c\x04',
    ],
    (Ecu.eps, 0x746, None): [
      b'}\xc0\x10\x00',
      b'm\xc0\x10\x00',
    ],
    (Ecu.fwdCamera, 0x787, None): [
      b'\x00\x00\x64\x35\x1f\x40\x20\x09',
      b'\x00\x00c\xe9\x1f@ \x03',
      b'\x00\x00d\xd3\x1f@ \t',
    ],
    (Ecu.engine, 0x7e0, None): [
      b'\xba"@p\a',
      b'\xa7)\xa0q\a',
      b'\xf1\x82\xa7)\xa0q\a',
      b'\xba"@@\a',
    ],
    (Ecu.transmission, 0x7e1, None): [
      b'\xdc\xf2\x60\x60\x00',
      b'\xdc\xf2@`\x00',
      b'\xda\xfd\xe0\x80\x00',
      b'\xdc\xf2`\x81\000',
      b'\xdc\xf2`\x80\x00',
      b'\x1a\xf6F`\x00',
    ],
  },
  CAR.LEGACY: {
    # Ecu, addr, subaddr: ROM ID
    (Ecu.esp, 0x7b0, None): [
      b'\x00',
    ],
    (Ecu.eps, 0x746, None): [
      b'\x00',
    ],
    (Ecu.fwdCamera, 0x787, None): [
      b'\x00',
    ],
    (Ecu.engine, 0x7e0, None): [
      b'\x00',
    ],
    (Ecu.transmission, 0x7e1, None): [
      b'\x00',
    ],
  },
  CAR.LEGACY_PREGLOBAL: {
    (Ecu.esp, 0x7b0, None): [
      b'k\x00\x00',
    ],
    (Ecu.eps, 0x746, None): [
      b'[\x00\x00\x00',
    ],
    (Ecu.fwdCamera, 0x787, None): [
      b'\x00\x00',
    ],
    (Ecu.engine, 0x7e0, None): [
      b'\x00',
    ],
    (Ecu.transmission, 0x7e1, None): [
      b'\x00',
    ],
  },
  CAR.LEGACY_PREGLOBAL_2018: {
    # 2018 Subaru Legacy 2.5i Premium - UDM / @kram322
    # 2018 Subaru Legacy - UDM / @Hassan
    # 2018 Subaru Legacy - UDM / @Brycey92
    # Ecu, addr, subaddr: ROM ID
    (Ecu.esp, 0x7b0, None): [
      b'\x00',
    ],
    (Ecu.eps, 0x746, None): [
      b'{\x00',
    ],
    (Ecu.fwdCamera, 0x787, None): [
      b'\x00\x00',
    ],
    (Ecu.engine, 0x7e0, None): [
      b'\x00',
    ],
    (Ecu.transmission, 0x7e1, None): [
      b'\x00\x00',
    ],
  },
  CAR.LEVORG_PREGLOBAL: {
     # 2016 Subaru Levorg / @jpgnz
     # Ecu, addr, subaddr: ROM ID
     (Ecu.esp, 0x7b0, None): [
       b'j\x00\x00\000',
     ],
     (Ecu.eps, 0x746, None): [
       b'Z\x00\000\000',
     ],
     (Ecu.fwdCamera, 0x787, None): [
       b'\000\000',
     ],
     (Ecu.engine, 0x7e0, None): [
       b'\x00\x00',
     ],
     (Ecu.transmission, 0x7e1, None): [
       b'\x00\x00',
     ],
  },
  CAR.OUTBACK: {
    # 2020 Outback 2.4 XT Limited - UDM / @KingChalupa
    # 2020 Outback 2.5i Premium - UDM / @ursubpar
    # 2021 Outback - UDM / @Frye - FL
    # 2020 Outback 2.4 Touring XT  - UDM / @chrissantamaria
    # 2022 Outback - UDM / @atran913
    # 2022 Outback - UDM / @duchuy1993
    # 2022 Outback XT Touring - UDM / @cook.w.ryan
    # Ecu, addr, subaddr: ROM ID
    (Ecu.esp, 0x7b0, None): [
      b'\xa1  \x00\x00',
    ],
    (Ecu.eps, 0x746, None): [
      b'\x00\x00\x00\x00',
    ],
    (Ecu.fwdCamera, 0x787, None): [
      b'\x00\x00',
    ],
    (Ecu.engine, 0x7e0, None): [
      b'\x00\x00',
    ],
    (Ecu.transmission, 0x7e1, None): [
      b'\x00\x00',
    ],
  },
  CAR.OUTBACK_PREGLOBAL: {
    (Ecu.esp, 0x7b0, None): [
      b'{\x00\x00\x00',
    ],
    (Ecu.eps, 0x746, None): [
      b'k\x00\x00\x00',
    ],
    (Ecu.fwdCamera, 0x787, None): [
      b'\x00\x00',
    ],
    (Ecu.engine, 0x7e0, None): [
      b'\x00',
    ],
    (Ecu.transmission, 0x7e1, None): [
      b'\x00\x00',
    ],
  },
  CAR.OUTBACK_PREGLOBAL_2018: {
    (Ecu.esp, 0x7b0, None): [
      b'\x8b\x97\xac\x00',
      b'\x8b\x9a\xac\x00',
      b'\x9b\x97\xac\x00',
      b'\x8b\x97\xbc\x00',
      b'\x8b\x99\xac\x00',
      b'\x9b\x9a\xac\000',
      b'\x9b\x97\xbe\x10',
    ],
    (Ecu.eps, 0x746, None): [
      b'{\xb0\x00\x00',
      b'{\xb0\x00\x01',
    ],
    (Ecu.fwdCamera, 0x787, None): [
      b'\x00\x00df\x1f@ \n',
      b'\x00\x00d\xfe\x1f@ \x15',
      b'\x00\x00d\x95\x00\x00\x00\x00',
      b'\x00\x00d\x95\x1f@ \x0f',
      b'\x00\x00d\xfe\x00\x00\x00\x00',
      b'\x00\x00e\x19\x1f@ \x15',
      b'\x00\x00df\x00\x00\x00\x00',
    ],
    (Ecu.engine, 0x7e0, None): [
      b'\xb5"@p\a',
      b'\xb5+@@\a',
      b'\xb5"@P\a',
      b'\xc4"@0\a',
      b'\xb5b@1\x07',
      b'\xb5q\xe0@\a',
      b'\xc4+@0\a',
      b'\xc4b@p\a',
    ],
    (Ecu.transmission, 0x7e1, None): [
      b'\xbc\xf2@\x81\x00',
      b'\xbc\xfb\xe0\x80\x00',
      b'\xbc\xf2@\x80\x00',
      b'\xbb\xf2@`\x00',
      b'\xbc\xe2@\x80\x00',
      b'\xbc\xfb\xe0`\x00',
      b'\xbc\xaf\xe0`\x00',
      b'\xbb\xfb\xe0`\000',
      b'\xbe\xe2@`\x00',
    ],
  },
  CAR.WRX_PREGLOBAL: {
    # 2018 Subaru WRX / @cferra
    # 2016 Subaru WRX / @Hexinator
    # Ecu, addr, subaddr: ROM ID
    (Ecu.esp, 0x7b0, None): [
      b'\x00\x00\x00',
    ],
    (Ecu.eps, 0x746, None): [
      b'z\x00\x00\x00',
    ],
    (Ecu.fwdCamera, 0x787, None): [
      b'\x00\x00',
    ],
    (Ecu.engine, 0x7e0, None): [
      b'\x00\x00',
    ],
    (Ecu.transmission, 0x7e1, None): [
      b'\x00\x00',
    ],
  },
}


STEER_THRESHOLD = {
  CAR.ASCENT: 80,
  CAR.IMPREZA: 80,
  CAR.IMPREZA_2020: 80,
  CAR.CROSSTREK_2020H: 80,
  CAR.FORESTER: 80,
  CAR.FORESTER_2020H: 80,
  CAR.FORESTER_PREGLOBAL: 75,
  CAR.LEGACY: 80,
  CAR.LEGACY_PREGLOBAL: 75,
  CAR.LEGACY_PREGLOBAL_2018: 75,
  CAR.LEVORG_PREGLOBAL: 75,
  CAR.OUTBACK: 80,
  CAR.OUTBACK_PREGLOBAL: 75,
  CAR.OUTBACK_PREGLOBAL_2018: 75,
  CAR.WRX_PREGLOBAL: 75,
}

DBC = {
  CAR.ASCENT: dbc_dict('subaru_global_2017_generated', None),
  CAR.IMPREZA: dbc_dict('subaru_global_2017_generated', None),
  CAR.IMPREZA_2020: dbc_dict('subaru_global_2017_generated', None),
  CAR.CROSSTREK_2020H: dbc_dict('subaru_global_2020_hybrid_generated', None),
  CAR.FORESTER: dbc_dict('subaru_global_2017_generated', None),
  CAR.FORESTER_2020H: dbc_dict('subaru_global_2017_generated', None),
  CAR.FORESTER_PREGLOBAL: dbc_dict('subaru_forester_2017_generated', None),
  CAR.LEGACY: dbc_dict('subaru_global_2017_generated', None),
  CAR.LEGACY_PREGLOBAL: dbc_dict('subaru_outback_2015_generated', None),
  CAR.LEGACY_PREGLOBAL_2018: dbc_dict('subaru_outback_2019_generated', None),
  CAR.LEVORG_PREGLOBAL: dbc_dict('subaru_forester_2017_generated', None),
  CAR.OUTBACK: dbc_dict('subaru_global_2017_generated', None),
  CAR.OUTBACK_PREGLOBAL: dbc_dict('subaru_outback_2015_generated', None),
  CAR.OUTBACK_PREGLOBAL_2018: dbc_dict('subaru_outback_2019_generated', None),
  CAR.WRX_PREGLOBAL: dbc_dict('subaru_forester_2017_generated', None),
}

PREGLOBAL_CARS = [CAR.FORESTER_PREGLOBAL, CAR.LEGACY_PREGLOBAL, CAR.LEGACY_PREGLOBAL_2018, CAR.LEVORG_PREGLOBAL, CAR.OUTBACK_PREGLOBAL, CAR.OUTBACK_PREGLOBAL_2018, CAR.WRX_PREGLOBAL]
GLOBAL_CARS_SNG = [CAR.ASCENT, CAR.IMPREZA, CAR.IMPREZA_2020, CAR.FORESTER, CAR.FORESTER_2020H]
