"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import numpy as np
import pyray as rl

from openpilot.selfdrive.ui.ui_state import ui_state, UIStatus
from openpilot.selfdrive.ui.sunnypilot.onroad.rainbow_path import RainbowPath
from openpilot.selfdrive.ui.sunnypilot.ui_state import MADSState

LANE_LINE_COLORS_SP = {
  UIStatus.LAT_ONLY: rl.Color(0, 255, 64, 255),
  UIStatus.LONG_ONLY: rl.Color(0, 255, 64, 255),
}


class ModelRendererSP:
  def __init__(self):
    self.rainbow_path = RainbowPath()

  @property
  def _lateral_active(self) -> bool:
    sm = ui_state.sm
    if sm.valid["selfdriveStateSP"]:
      mads = sm["selfdriveStateSP"].mads
      if mads.available:
        return mads.enabled and mads.state != MADSState.paused
    return ui_state.status in (UIStatus.ENGAGED, UIStatus.LAT_ONLY)

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

    lane_lines = getattr(model, "laneLines", [])
    probs = getattr(model, "laneLineProbs", [])
    stds = getattr(model, "laneLineStds", [])
    road_edges = getattr(model, "roadEdges", [])
    road_edge_stds = getattr(model, "roadEdgeStds", [])

    lookahead = float(np.clip(v_ego, 8.0, 35.0))
    pos_x = np.asarray(model.position.x, dtype=float)
    pos_y = np.asarray(model.position.y, dtype=float)
    if pos_x.size < 2 or not (pos_x[0] <= lookahead <= pos_x[-1]):
      return -1

    def _get_boundary(ll, prob, std, re, re_std):
      if ll is not None and prob is not None and std is not None:
        try:
          if 0.6 <= float(prob) <= 1.0 and 0.0 <= float(std) <= 0.3:
            x = np.asarray(ll.x, dtype=float)
            y = np.asarray(ll.y, dtype=float)
            if x.size >= 2 and x[0] <= lookahead <= x[-1]:
              return x, y
        except (AttributeError, IndexError, TypeError, ValueError):
          pass

      if re is not None and re_std is not None:
        try:
          if 0.0 <= float(re_std) <= 0.3:
            x = np.asarray(re.x, dtype=float)
            y = np.asarray(re.y, dtype=float)
            if x.size >= 2 and x[0] <= lookahead <= x[-1]:
              return x, y
        except (AttributeError, IndexError, TypeError, ValueError):
          pass

      return None, None

    left_ll = lane_lines[1] if len(lane_lines) > 1 else None
    left_prob = probs[1] if len(probs) > 1 else None
    left_std = stds[1] if len(stds) > 1 else None
    left_re = road_edges[0] if len(road_edges) > 0 else None
    left_re_std = road_edge_stds[0] if len(road_edge_stds) > 0 else None

    left_x, left_y = _get_boundary(left_ll, left_prob, left_std, left_re, left_re_std)
    if left_x is None or left_y is None:
      return -1

    right_ll = lane_lines[2] if len(lane_lines) > 2 else None
    right_prob = probs[2] if len(probs) > 2 else None
    right_std = stds[2] if len(stds) > 2 else None
    right_re = road_edges[1] if len(road_edges) > 1 else None
    right_re_std = road_edge_stds[1] if len(road_edge_stds) > 1 else None

    right_x, right_y = _get_boundary(right_ll, right_prob, right_std, right_re, right_re_std)
    if right_x is None or right_y is None:
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
