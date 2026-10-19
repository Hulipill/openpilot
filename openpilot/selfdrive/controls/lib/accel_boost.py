import numpy as np
from openpilot.cereal import log
from openpilot.common.constants import CV
from openpilot.common.params import Params
from openpilot.common.realtime import DT_MDL
from openpilot.sunnypilot import PARAMS_UPDATE_PERIOD, get_sanitize_int_param

ACCEL_BOOST_MAX = 0.5
ACCEL_BOOST_RATE = 0.05
ACCEL_BOOST_PER_OVERRIDE = 0.25
ACCEL_BOOST_MIN_SPEED = 10 * CV.MPH_TO_MS


def get_starting_boost(personality=log.LongitudinalPersonality.standard) -> float:
  if personality == log.LongitudinalPersonality.relaxed or str(personality) == "relaxed":
    return 0.25 * ACCEL_BOOST_MAX
  elif personality == log.LongitudinalPersonality.aggressive or str(personality) == "aggressive":
    return 0.75 * ACCEL_BOOST_MAX
  return 0.50 * ACCEL_BOOST_MAX


class AccelBoost:
  def __init__(self, params=None):
    self.params = params or Params()
    self.map_mode = bool(self.params.get("AccelBoostMapMode", return_default=True))
    self.map_min_speed = get_sanitize_int_param("AccelBoostMapMinSpeed", 20, 120, self.params)
    self.is_metric = bool(self.params.get_bool("IsMetric"))
    self.frame = -1
    self.total_boost = 0.0
    self.boost_this_override = 0.0
    self.boost_eligible = False
    self.prev_active = False
    self.prev_personality = None

  def _update_params(self):
    self.frame += 1
    if self.frame % int(PARAMS_UPDATE_PERIOD / DT_MDL) == 0:
      self.map_mode = bool(self.params.get("AccelBoostMapMode", return_default=True))
      self.map_min_speed = get_sanitize_int_param("AccelBoostMapMinSpeed", 20, 120, self.params)
      self.is_metric = bool(self.params.get_bool("IsMetric"))

  def _reset_boost(self):
    self.total_boost = 0.0
    self.boost_this_override = 0.0
    self.boost_eligible = False
    self.prev_active = False

  def update(self, sm, output_a_target_e2e, output_a_target_mpc, a_cruise):
    self._update_params()

    if self.map_mode:
      map_data = None
      if hasattr(sm, "data") and "liveMapDataSP" in sm.data:
        map_data = sm["liveMapDataSP"]
      elif hasattr(sm, "__getitem__"):
        try:
          map_data = sm["liveMapDataSP"]
        except (KeyError, IndexError, TypeError):
          map_data = None

      speed_limit_valid = (map_data is not None and
                           getattr(map_data, "speedLimitValid", False) and
                           getattr(map_data, "speedLimit", 0.0) > 0.0)
      if speed_limit_valid:
        speed_conv = CV.MS_TO_KPH if self.is_metric else CV.MS_TO_MPH
        speed_limit_user = round(map_data.speedLimit * speed_conv)
        if speed_limit_user < self.map_min_speed:
          self._reset_boost()
          return output_a_target_e2e
      else:
        self._reset_boost()
        return output_a_target_e2e

    mads_enabled = False
    if hasattr(sm, "data") and "selfdriveStateSP" in sm.data:
      mads_enabled = getattr(getattr(sm["selfdriveStateSP"], "mads", None), "enabled", False)
    elif hasattr(sm, "__getitem__"):
      try:
        mads_enabled = getattr(getattr(sm["selfdriveStateSP"], "mads", None), "enabled", False)
      except (KeyError, IndexError, TypeError):
        mads_enabled = False

    enabled = sm["selfdriveState"].enabled
    active = enabled or mads_enabled
    personality = getattr(sm["selfdriveState"], "personality", log.LongitudinalPersonality.standard)

    v_ego = sm["carState"].vEgo
    speed_scale = np.interp(
      v_ego, [ACCEL_BOOST_MIN_SPEED, 2 * ACCEL_BOOST_MIN_SPEED], [0.0, 1.0]
    )
    boost_scale = speed_scale * np.interp(
      output_a_target_e2e, [-1.0, -0.5, 5.0], [0.0, 1.0, 1.0], right=0.0
    )

    if not active:
      self._reset_boost()
      self.prev_active = False
      self.prev_personality = personality
      return output_a_target_e2e

    if not self.prev_active or personality != self.prev_personality:
      self.total_boost = get_starting_boost(personality)

    model_limited = (
      output_a_target_e2e + self.total_boost * boost_scale
      < min(output_a_target_mpc, a_cruise) - 0.1
    )

    gas_pressed = sm["carState"].gasPressed
    if not enabled or not gas_pressed:
      self.boost_this_override = 0.0
      # Latch eligibility before the override changes the lead plan.
      self.boost_eligible = bool(enabled and model_limited)

    if enabled and gas_pressed and self.boost_eligible:
      increase = min(
        ACCEL_BOOST_RATE * DT_MDL * speed_scale,
        ACCEL_BOOST_PER_OVERRIDE - self.boost_this_override,
        ACCEL_BOOST_MAX - self.total_boost,
      )
      self.total_boost += increase
      self.boost_this_override += increase

    self.prev_active = active
    self.prev_personality = personality

    return output_a_target_e2e + self.total_boost * boost_scale
