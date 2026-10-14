"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from unittest.mock import MagicMock, patch
from openpilot.sunnypilot.sunnylink.athena import sunnylinkd
from openpilot.common.test import OpenpilotTestCase


class TestSunnylinkdMethods(OpenpilotTestCase):
  def setup_method(self):
    self.saved_params = []

    self.original_save = sunnylinkd.save_param_from_base64_encoded_string

    def mock_save_param(key, value, compression=False):
      self.saved_params.append((key, value, compression))

    sunnylinkd.save_param_from_base64_encoded_string = mock_save_param  # ty: ignore[invalid-assignment]

  def teardown_method(self):
    sunnylinkd.save_param_from_base64_encoded_string = self.original_save  # ty: ignore[invalid-assignment]

  def test_saveParams_blocked(self):
    blocked_params = {
      "GithubUsername": "attacker",
      "GithubSshKeys": "ssh-rsa attacker_key",
    }

    sunnylinkd.saveParams(blocked_params)

    assert len(self.saved_params) == 0

  def test_saveParams_allowed(self):
    allowed_params = {
      "SpeedLimitOffset": "5",
      "MyCustomParam": "123"
    }

    sunnylinkd.saveParams(allowed_params)

    # verify content
    assert len(self.saved_params) == 2
    keys_saved = [p[0] for p in self.saved_params]
    assert "SpeedLimitOffset" in keys_saved
    assert "MyCustomParam" in keys_saved

  def test_saveParams_mixed(self):
    mixed_params = {
      "GithubUsername": "attacker",
      "SpeedLimitOffset": "10"
    }

    sunnylinkd.saveParams(mixed_params)

    # should save allowed one
    assert len(self.saved_params) == 1
    assert self.saved_params[0][0] == "SpeedLimitOffset"
    assert self.saved_params[0][1] == "10"

  def test_getParamsMetadata_default_big_model(self):
    import base64
    import gzip
    import json
    from openpilot.sunnypilot.models.model_name import DEFAULT_BIG_MODEL

    with patch("openpilot.sunnypilot.sunnylink.athena.sunnylinkd.chestnut_present", return_value=False), \
         patch("openpilot.sunnypilot.sunnylink.athena.sunnylinkd.jetlink_adapter.status", return_value=None):
      meta = json.loads(gzip.decompress(base64.b64decode(sunnylinkd.getParamsMetadata())))
      self.assertEqual(meta["default_big_model"], DEFAULT_BIG_MODEL)

    status_mock = MagicMock()
    status_mock.default_model = "custom_big_model"
    with patch("openpilot.sunnypilot.sunnylink.athena.sunnylinkd.chestnut_present", return_value=False), \
         patch("openpilot.sunnypilot.sunnylink.athena.sunnylinkd.jetlink_adapter.status", return_value=status_mock):
      meta = json.loads(gzip.decompress(base64.b64decode(sunnylinkd.getParamsMetadata())))
      self.assertEqual(meta["default_big_model"], "custom_big_model")

    # If chestnut is present, always DEFAULT_BIG_MODEL
    with patch("openpilot.sunnypilot.sunnylink.athena.sunnylinkd.chestnut_present", return_value=True), \
         patch("openpilot.sunnypilot.sunnylink.athena.sunnylinkd.jetlink_adapter.status", return_value=status_mock):
      meta = json.loads(gzip.decompress(base64.b64decode(sunnylinkd.getParamsMetadata())))
      self.assertEqual(meta["default_big_model"], DEFAULT_BIG_MODEL)
