from unittest.mock import MagicMock
from openpilot.cereal import log
from openpilot.common.constants import CV
from openpilot.common.test import OpenpilotTestCase
from openpilot.selfdrive.controls.lib.accel_boost import (
  ACCEL_BOOST_MAX,
  AccelBoost,
  get_starting_boost,
)


def create_sm(enabled=True, gas_pressed=False, v_ego=20.0, speed_limit_valid=True, speed_limit_ms=30.0,
              personality=log.LongitudinalPersonality.standard, mads_enabled=False):
  map_mock = MagicMock(speedLimitValid=speed_limit_valid, speedLimit=speed_limit_ms)
  mock_dict = {
    'selfdriveState': MagicMock(enabled=enabled, personality=personality),
    'selfdriveStateSP': MagicMock(mads=MagicMock(enabled=mads_enabled)),
    'carState': MagicMock(gasPressed=gas_pressed, vEgo=v_ego),
    'liveMapDataSP': map_mock,
  }
  sm = MagicMock()
  sm.__getitem__.side_effect = lambda k: mock_dict[k]
  sm.data = mock_dict
  sm.__contains__.side_effect = lambda k: k in mock_dict
  return sm


class TestAccelBoost(OpenpilotTestCase):
  def test_starting_boost_values(self):
    self.assertAlmostEqual(get_starting_boost(log.LongitudinalPersonality.relaxed), 0.25 * ACCEL_BOOST_MAX)
    self.assertAlmostEqual(get_starting_boost(log.LongitudinalPersonality.standard), 0.50 * ACCEL_BOOST_MAX)
    self.assertAlmostEqual(get_starting_boost(log.LongitudinalPersonality.aggressive), 0.75 * ACCEL_BOOST_MAX)

    self.assertAlmostEqual(get_starting_boost("relaxed"), 0.25 * ACCEL_BOOST_MAX)
    self.assertAlmostEqual(get_starting_boost("standard"), 0.50 * ACCEL_BOOST_MAX)
    self.assertAlmostEqual(get_starting_boost("aggressive"), 0.75 * ACCEL_BOOST_MAX)

  def test_boost_always_enabled_and_personality_starting_boost(self):
    mock_params = MagicMock()
    mock_params.get.side_effect = lambda k, return_default=False: False
    mock_params.get_bool.side_effect = lambda k: False
    ab = AccelBoost(params=mock_params)
    self.assertFalse(ab.map_mode)

    # Initial frame: starts at standard boost (0.50 * 0.5 = 0.25)
    sm = create_sm(enabled=True, gas_pressed=False, v_ego=15.0, personality=log.LongitudinalPersonality.standard)
    out = ab.update(sm, output_a_target_e2e=0.5, output_a_target_mpc=2.0, a_cruise=2.0)
    self.assertTrue(ab.boost_eligible)
    self.assertAlmostEqual(ab.total_boost, 0.25)
    # v_ego = 15.0 > 2 * 4.47m/s -> speed_scale = 1.0, boost_scale = 1.0 -> out = 0.5 + 0.25 = 0.75
    self.assertAlmostEqual(out, 0.75)

    # Press gas -> boost should accumulate beyond starting boost
    sm = create_sm(enabled=True, gas_pressed=True, v_ego=15.0, personality=log.LongitudinalPersonality.standard)
    out = ab.update(sm, output_a_target_e2e=0.5, output_a_target_mpc=2.0, a_cruise=2.0)
    self.assertGreater(ab.total_boost, 0.25)
    self.assertGreater(out, 0.75)

  def test_personality_switch_updates_starting_boost(self):
    mock_params = MagicMock()
    mock_params.get.side_effect = lambda k, return_default=False: False
    mock_params.get_bool.side_effect = lambda k: False
    ab = AccelBoost(params=mock_params)

    # Standard
    sm = create_sm(enabled=True, gas_pressed=False, v_ego=15.0, personality=log.LongitudinalPersonality.standard)
    ab.update(sm, 0.5, 2.0, 2.0)
    self.assertAlmostEqual(ab.total_boost, 0.25)

    # Switch to Aggressive
    sm = create_sm(enabled=True, gas_pressed=False, v_ego=15.0, personality=log.LongitudinalPersonality.aggressive)
    ab.update(sm, 0.5, 2.0, 2.0)
    self.assertAlmostEqual(ab.total_boost, 0.375)

    # Switch to Relaxed
    sm = create_sm(enabled=True, gas_pressed=False, v_ego=15.0, personality=log.LongitudinalPersonality.relaxed)
    ab.update(sm, 0.5, 2.0, 2.0)
    self.assertAlmostEqual(ab.total_boost, 0.125)

  def test_disengagement_and_mads_retention(self):
    mock_params = MagicMock()
    mock_params.get.side_effect = lambda k, return_default=False: False
    mock_params.get_bool.side_effect = lambda k: False
    ab = AccelBoost(params=mock_params)

    # Active and engaged
    sm = create_sm(enabled=True, gas_pressed=False, v_ego=15.0, personality=log.LongitudinalPersonality.standard)
    ab.update(sm, 0.5, 2.0, 2.0)
    self.assertAlmostEqual(ab.total_boost, 0.25)

    # Cruise disengaged, but MADS enabled (lat_only) -> retains boost
    sm = create_sm(enabled=False, mads_enabled=True, gas_pressed=False, v_ego=15.0, personality=log.LongitudinalPersonality.standard)
    ab.update(sm, 0.5, 2.0, 2.0)
    self.assertAlmostEqual(ab.total_boost, 0.25)

    # Completely inactive (both enabled and MADS false) -> resets to 0.0
    sm = create_sm(enabled=False, mads_enabled=False, gas_pressed=False, v_ego=15.0, personality=log.LongitudinalPersonality.standard)
    out = ab.update(sm, 0.5, 2.0, 2.0)
    self.assertEqual(ab.total_boost, 0.0)
    self.assertEqual(out, 0.5)

    # Re-engage -> back to starting boost
    sm = create_sm(enabled=True, gas_pressed=False, v_ego=15.0, personality=log.LongitudinalPersonality.standard)
    ab.update(sm, 0.5, 2.0, 2.0)
    self.assertAlmostEqual(ab.total_boost, 0.25)

  def test_map_mode_disabled_boosts_regardless_of_speed_limit(self):
    mock_params = MagicMock()
    mock_params.get.side_effect = lambda k, return_default=False: False
    mock_params.get_bool.side_effect = lambda k: False
    ab = AccelBoost(params=mock_params)
    self.assertFalse(ab.map_mode)

    # Even with low speed limit (e.g. 20 mph), boost works because map_mode is False
    sm = create_sm(enabled=True, gas_pressed=False, v_ego=15.0, speed_limit_ms=20.0 * CV.MPH_TO_MS)
    out = ab.update(sm, 0.5, 2.0, 2.0)
    self.assertTrue(ab.boost_eligible)
    self.assertAlmostEqual(ab.total_boost, 0.25)
    self.assertAlmostEqual(out, 0.75)

    sm = create_sm(enabled=True, gas_pressed=True, v_ego=15.0, speed_limit_ms=20.0 * CV.MPH_TO_MS)
    out = ab.update(sm, 0.5, 2.0, 2.0)
    self.assertGreater(ab.total_boost, 0.25)
    self.assertGreater(out, 0.75)

  def test_map_mode_below_min_speed_gates_boost_off(self):
    mock_params = MagicMock()
    mock_params.get.side_effect = lambda k, return_default=False: True if k == "AccelBoostMapMode" else 50
    mock_params.get_bool.side_effect = lambda k: False  # is_metric = False (mph)
    ab = AccelBoost(params=mock_params)
    self.assertTrue(ab.map_mode)
    self.assertEqual(ab.map_min_speed, 50)

    # Road speed limit is 30 mph (< 50 mph threshold)
    sm = create_sm(enabled=True, gas_pressed=False, v_ego=15.0, speed_limit_ms=30.0 * CV.MPH_TO_MS)
    out = ab.update(sm, 0.5, 2.0, 2.0)
    self.assertEqual(ab.total_boost, 0.0)
    self.assertFalse(ab.boost_eligible)
    self.assertEqual(out, 0.5)

    sm = create_sm(enabled=True, gas_pressed=True, v_ego=15.0, speed_limit_ms=30.0 * CV.MPH_TO_MS)
    out = ab.update(sm, 0.5, 2.0, 2.0)
    self.assertEqual(ab.total_boost, 0.0)
    self.assertEqual(out, 0.5)

  def test_map_mode_at_or_above_min_speed_allows_boost(self):
    mock_params = MagicMock()
    mock_params.get.side_effect = lambda k, return_default=False: True if k == "AccelBoostMapMode" else 50
    mock_params.get_bool.side_effect = lambda k: False
    ab = AccelBoost(params=mock_params)
    self.assertTrue(ab.map_mode)
    self.assertEqual(ab.map_min_speed, 50)

    # Road speed limit is 55 mph (>= 50 mph threshold)
    sm = create_sm(enabled=True, gas_pressed=False, v_ego=15.0, speed_limit_ms=55.0 * CV.MPH_TO_MS)
    out = ab.update(sm, 0.5, 2.0, 2.0)
    self.assertTrue(ab.boost_eligible)
    self.assertAlmostEqual(ab.total_boost, 0.25)
    self.assertAlmostEqual(out, 0.75)

    sm = create_sm(enabled=True, gas_pressed=True, v_ego=15.0, speed_limit_ms=55.0 * CV.MPH_TO_MS)
    out = ab.update(sm, 0.5, 2.0, 2.0)
    self.assertGreater(ab.total_boost, 0.25)
    self.assertGreater(out, 0.75)

  def test_map_mode_unmapped_speed_limit_gates_boost_off(self):
    mock_params = MagicMock()
    mock_params.get.side_effect = lambda k, return_default=False: True if k == "AccelBoostMapMode" else 50
    mock_params.get_bool.side_effect = lambda k: False
    ab = AccelBoost(params=mock_params)

    # Road has speedLimitValid = False
    sm = create_sm(enabled=True, gas_pressed=False, v_ego=15.0, speed_limit_valid=False, speed_limit_ms=0.0)
    out = ab.update(sm, 0.5, 2.0, 2.0)
    self.assertEqual(ab.total_boost, 0.0)
    self.assertFalse(ab.boost_eligible)
    self.assertEqual(out, 0.5)

    sm = create_sm(enabled=True, gas_pressed=True, v_ego=15.0, speed_limit_valid=False, speed_limit_ms=0.0)
    out = ab.update(sm, 0.5, 2.0, 2.0)
    self.assertEqual(ab.total_boost, 0.0)
    self.assertEqual(out, 0.5)

  def test_map_mode_metric_conversion(self):
    mock_params = MagicMock()
    mock_params.get.side_effect = lambda k, return_default=False: True if k == "AccelBoostMapMode" else 80
    mock_params.get_bool.side_effect = lambda k: True  # is_metric = True (km/h)
    ab = AccelBoost(params=mock_params)
    self.assertTrue(ab.is_metric)
    self.assertEqual(ab.map_min_speed, 80)

    # 70 km/h (< 80 km/h) -> gated off
    sm_slow = create_sm(enabled=True, gas_pressed=False, v_ego=15.0, speed_limit_ms=70.0 * CV.KPH_TO_MS)
    out = ab.update(sm_slow, 0.5, 2.0, 2.0)
    self.assertEqual(ab.total_boost, 0.0)
    self.assertFalse(ab.boost_eligible)
    self.assertEqual(out, 0.5)

    # 90 km/h (>= 80 km/h) -> allowed
    sm_fast_unpressed = create_sm(enabled=True, gas_pressed=False, v_ego=15.0, speed_limit_ms=90.0 * CV.KPH_TO_MS)
    out = ab.update(sm_fast_unpressed, 0.5, 2.0, 2.0)
    self.assertTrue(ab.boost_eligible)
    self.assertAlmostEqual(ab.total_boost, 0.25)
    self.assertAlmostEqual(out, 0.75)

    sm_fast_pressed = create_sm(enabled=True, gas_pressed=True, v_ego=15.0, speed_limit_ms=90.0 * CV.KPH_TO_MS)
    out = ab.update(sm_fast_pressed, 0.5, 2.0, 2.0)
    self.assertGreater(ab.total_boost, 0.25)
    self.assertGreater(out, 0.75)

  def test_param_toggle_at_runtime(self):
    map_mode = False
    mock_params = MagicMock()
    mock_params.get.side_effect = lambda k, return_default=False: map_mode if k == "AccelBoostMapMode" else 50
    mock_params.get_bool.side_effect = lambda k: False
    ab = AccelBoost(params=mock_params)
    self.assertFalse(ab.map_mode)

    # Speed limit 30 mph: allowed because map_mode is False
    sm_unpressed = create_sm(enabled=True, gas_pressed=False, v_ego=15.0, speed_limit_ms=30.0 * CV.MPH_TO_MS)
    out = ab.update(sm_unpressed, 0.5, 2.0, 2.0)
    self.assertTrue(ab.boost_eligible)
    self.assertAlmostEqual(ab.total_boost, 0.25)
    self.assertAlmostEqual(out, 0.75)

    # Enable map mode dynamically at runtime
    map_mode = True
    ab.frame = 59  # Next frame will trigger periodic update
    out = ab.update(sm_unpressed, 0.5, 2.0, 2.0)
    self.assertTrue(ab.map_mode)
    # Now gated off because 30 < 50
    self.assertEqual(ab.total_boost, 0.0)
    self.assertEqual(out, 0.5)
