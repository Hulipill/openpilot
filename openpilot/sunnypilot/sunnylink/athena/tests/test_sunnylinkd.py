"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from unittest.mock import MagicMock, patch

from openpilot.common.test import OpenpilotTestCase
from openpilot.sunnypilot.sunnylink.athena import sunnylinkd


class TestSunnylinkdMethods(OpenpilotTestCase):
  def setUp(self):
    super().setUp()
    self.saved_params = []

    def mock_save_param(key, value, compression=False):
      self.saved_params.append((key, value, compression))

    save_patcher = patch.object(sunnylinkd, 'save_param_from_base64_encoded_string', mock_save_param)
    save_patcher.start()
    self.addCleanup(save_patcher.stop)

    # Mock params with IsEngaged=False and SunnylinkAllowSensitiveWrite=False by default
    self.mock_params = MagicMock()
    self.mock_params.get_bool.return_value = False

    params_patcher = patch.object(sunnylinkd, 'params', self.mock_params)
    params_patcher.start()
    self.addCleanup(params_patcher.stop)

  def test_saveParams_always_blocked(self):
    blocked_params = {
      "GithubUsername": "attacker",
      "GithubSshKeys": "ssh-rsa attacker_key",
    }

    sunnylinkd.saveParams(blocked_params)

    self.assertEqual(len(self.saved_params), 0)

  def test_saveParams_allowed(self):
    allowed_params = {
      "SpeedLimitOffset": "5",
      "MyCustomParam": "123"
    }

    sunnylinkd.saveParams(allowed_params)

    # verify content
    self.assertEqual(len(self.saved_params), 2)
    keys_saved = [p[0] for p in self.saved_params]
    self.assertIn("SpeedLimitOffset", keys_saved)
    self.assertIn("MyCustomParam", keys_saved)

  def test_saveParams_mixed(self):
    mixed_params = {
      "GithubUsername": "attacker",
      "SpeedLimitOffset": "10"
    }

    sunnylinkd.saveParams(mixed_params)

    # should save allowed one
    self.assertEqual(len(self.saved_params), 1)
    self.assertEqual(self.saved_params[0][0], "SpeedLimitOffset")
    self.assertEqual(self.saved_params[0][1], "10")

  def test_saveParams_always_blocked_sensitive_enabled(self):
    """GithubSshKeys, GithubUsername remain blocked even with toggle enabled"""
    self.mock_params.get_bool.side_effect = lambda key: key == "SunnylinkAllowSensitiveWrite"

    sunnylinkd.saveParams({
      "GithubUsername": "attacker",
      "GithubSshKeys": "ssh-rsa attacker_key",
      "SunnylinkAllowSensitiveWrite": "1",
    })

    self.assertEqual(len(self.saved_params), 0)

  # === SENSITIVE_PARAMS ===

  def test_saveParams_sensitive_blocked_by_default(self):
    """Sensitive params are blocked when toggle is disabled"""
    sunnylinkd.saveParams({
      "SshEnabled": "1",
      "AdbEnabled": "1",
      "EnableCopyparty": "1",
      "GsmApn": "attacker.apn",
      "EnableGithubRunner": "1",
      "DisableUpdates": "1",
      "LongitudinalManeuverMode": "1",
      "JoystickDebugMode": "1",
      "RecordFront": "1",
      "RecordAudio": "1",
      "RecordAudioFeedback": "1",
      "SunnylinkDongleId": "fake_sunnylink_id",
      "DongleId": "fake_dongle",
      "AccessToken": "fake_token",
      "HasAcceptedTerms": "0",
      "CompletedTrainingVersion": "0",
    })

    self.assertEqual(len(self.saved_params), 0)

  def test_saveParams_sensitive_allowed_with_toggle_enabled(self):
    """Sensitive params are allowed when toggle is enabled"""
    self.mock_params.get_bool.side_effect = lambda key: key == "SunnylinkAllowSensitiveWrite"

    sunnylinkd.saveParams({
      "SshEnabled": "1",
      "RecordFront": "1",
      "DongleId": "new_dongle",
    })

    self.assertEqual(len(self.saved_params), 3)

  # === Engaged state tests ===

  def test_saveParams_all_blocked_when_engaged(self):
    """All params are blocked while engaged"""
    self.mock_params.get_bool.side_effect = lambda key: key == "IsEngaged"

    sunnylinkd.saveParams({
      "Mads": "1",
      "AlphaLongitudinalEnabled": "1",
    })

    self.assertEqual(len(self.saved_params), 0)

  def test_saveParams_safety_critical_blocked_when_engaged(self):
    """Safety-critical params are blocked while engaged"""
    self.mock_params.get_bool.side_effect = lambda key: key == "IsEngaged"

    sunnylinkd.saveParams({
      "DoReboot": "1",
      "DoShutdown": "1",
      "DoUninstall": "1",
      "ForcePowerDown": "1",
      "OffroadMode": "1",
    })

    self.assertEqual(len(self.saved_params), 0)

  def test_saveParams_allowed_when_not_engaged(self):
    """Safety-critical params are allowed when not engaged"""
    sunnylinkd.saveParams({
      "DoReboot": "1",
      "DoShutdown": "1",
      "DoUninstall": "1",
      "ForcePowerDown": "1",
      "OffroadMode": "1",
      "Mads": "1",
      "AlphaLongitudinalEnabled": "1",
    })

    self.assertEqual(len(self.saved_params), 7)
