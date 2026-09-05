"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from openpilot.common.filter_simple import FirstOrderFilter
from openpilot.selfdrive.ui.ui_state import ui_state, UIStatus
from openpilot.selfdrive.ui.sunnypilot.onroad.chevron_metrics import ChevronMetrics
from openpilot.selfdrive.ui.sunnypilot.onroad.rainbow_path import RainbowPath
from openpilot.selfdrive.ui.sunnypilot.ui_state import MADSState
from openpilot.system.ui.lib.application import gui_app


class ModelRendererSP:
  def __init__(self):
    self.rainbow_path = RainbowPath()
    self.chevron_metrics = ChevronMetrics()
    self._width_filter = FirstOrderFilter(0.9, 0.1, 1 / gui_app.target_fps)

  @property
  def _lateral_active(self) -> bool:
    sm = ui_state.sm
    if sm.valid["selfdriveStateSP"]:
      mads = sm["selfdriveStateSP"].mads
      if mads.available:
        return mads.enabled and mads.state != MADSState.paused
    return ui_state.status in (UIStatus.ENGAGED, UIStatus.LAT_ONLY)

  def _get_path_half_width(self) -> float:
    target = 0.9 if self._lateral_active else 0.40
    return self._width_filter.update(target)

  def get_lane_centering_bias(self, sm) -> int:
    if not ui_state.lane_centering or not self._lateral_active:
      return -1

    if not sm.valid.get("modelV2", False) or not sm.valid.get("carState", False):
      return -1

    v_ego = max(sm["carState"].vEgo, 0.0)
    if v_ego < 5.0:
      return -1

    model = sm["modelV2"]
    if hasattr(model, "meta") and model.meta.laneChangeState != 0:
      return -1

    lane_lines = model.laneLines
    probs = model.laneLineProbs
    stds = model.laneLineStds
    if len(lane_lines) < 3 or len(probs) < 3 or len(stds) < 3:
      return -1

    if probs[1] < 0.6 or probs[2] < 0.6 or stds[1] > 0.3 or stds[2] > 0.3:
      return -1

    left_x = np.asarray(lane_lines[1].x, dtype=float)
    left_y = np.asarray(lane_lines[1].y, dtype=float)
    right_x = np.asarray(lane_lines[2].x, dtype=float)
    right_y = np.asarray(lane_lines[2].y, dtype=float)
    pos_x = np.asarray(model.position.x, dtype=float)
    pos_y = np.asarray(model.position.y, dtype=float)

    if left_x.size < 2 or right_x.size < 2 or pos_x.size < 2:
      return -1

    lookahead = float(np.clip(v_ego, 8.0, 35.0))
    if not (left_x[0] <= lookahead <= left_x[-1] and right_x[0] <= lookahead <= right_x[-1] and pos_x[0] <= lookahead <= pos_x[-1]):
      return -1

    left = float(np.interp(lookahead, left_x, left_y))
    right = float(np.interp(lookahead, right_x, right_y))
    width = right - left
    if not 2.6 <= width <= 4.8:
      return -1

    offset = float(ui_state.params.get("LaneCenterOffset", return_default=True) or 0.0)
    max_safe_offset = min(0.3, max(0.0, width * 0.5 - 1.1))
    target_y = 0.5 * (left + right) + float(np.clip(offset, -max_safe_offset, max_safe_offset))
    model_y = float(np.interp(lookahead, pos_x, pos_y))
    error = target_y - model_y

    if error < -0.08:
      return 1  # biasing left
    elif error > 0.08:
      return 2  # biasing right

    return -1
