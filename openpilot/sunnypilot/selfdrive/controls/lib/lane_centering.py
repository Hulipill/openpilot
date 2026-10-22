"""
Ported from StarPilot (https://github.com/StarPilot-Org/StarPilot)
Original LaneCenteringController implementation by the StarPilot team.
Licensed under the MIT License.
"""
from openpilot.cereal import log
import numpy as np

from openpilot.common.realtime import DT_CTRL
from openpilot.selfdrive.controls.lib.drive_helpers import smooth_value


_MIN_V_EGO = 5.0
_MIN_LANE_PROB = 0.6
_MAX_LANE_STD = 0.3
_MAX_ROAD_EDGE_STD = 0.3
_MIN_LANE_WIDTH = 2.6
_MAX_LANE_WIDTH = 4.8
_MAX_OFFSET = 0.3
_MIN_CENTER_TO_LINE = 1.1
_MAX_RAW_CORRECTION = 0.004
_MAX_GAIN = 0.30
_SMOOTH_TAU = 0.4
_SIGNAL_RELEASE_TAU = 0.20
_CONFIDENCE_RELEASE_TAU = 0.20
_CENTER_ERROR_DEADBAND = 0.08

_E2E_MAX_PATH_STD = 0.35
_E2E_BREAK_IN_START = 0.15
_E2E_BREAK_IN_FULL = 0.50


class LaneCenteringController:
  def __init__(self) -> None:
    self._correction = 0.0

  @property
  def correction(self) -> float:
    return self._correction

  def reset(self) -> None:
    self._correction = 0.0

  def update(self, model_curvature: float, model_v2, v_ego: float, enabled: bool, offset: float, e2e_authority: float,
             lat_active: bool, model_valid: bool, pause_on_signal: bool = False, turn_signal_active: bool = False) -> float:
    model_curvature = float(model_curvature)

    try:
      v_ego = float(v_ego)
      offset = float(offset)
      e2e_authority = float(e2e_authority)
    except (TypeError, ValueError):
      self.reset()
      return model_curvature

    if not np.isfinite([v_ego, offset, e2e_authority]).all():
      self.reset()
      return model_curvature

    if not model_valid or not enabled or not lat_active or v_ego < _MIN_V_EGO:
      self.reset()
      return model_curvature

    if pause_on_signal and turn_signal_active:
      self._correction = float(smooth_value(0.0, self._correction, _SIGNAL_RELEASE_TAU, dt=DT_CTRL))
      return model_curvature + self._correction

    try:
      if model_v2.meta.laneChangeState != log.LaneChangeState.off:
        self.reset()
        return model_curvature
    except (AttributeError, TypeError, ValueError):
      self.reset()
      return model_curvature

    valid, raw_correction = self._raw_correction(
      model_v2,
      v_ego,
      float(np.clip(offset, -_MAX_OFFSET, _MAX_OFFSET)),
      float(np.clip(e2e_authority, 0.0, 1.0)),
    )
    if not valid:
      self._correction = float(smooth_value(0.0, self._correction, _CONFIDENCE_RELEASE_TAU, dt=DT_CTRL))
      return model_curvature + self._correction

    target = float(np.clip(raw_correction, -_MAX_RAW_CORRECTION, _MAX_RAW_CORRECTION)) * _MAX_GAIN
    self._correction = float(smooth_value(target, self._correction, _SMOOTH_TAU, dt=DT_CTRL))
    return model_curvature + self._correction

  @staticmethod
  def _valid_path(x, y) -> bool:
    return bool(x.size >= 2 and x.size == y.size and np.isfinite(x).all() and np.isfinite(y).all() and np.all(np.diff(x) > 0))

  @staticmethod
  def _covers(x, distance: float) -> bool:
    return bool(x[0] <= distance <= x[-1])

  def _get_boundary(self, lane_line, prob, std, road_edge, road_edge_std, lookahead: float):
    # Try painted lane line first if confident
    if lane_line is not None and prob is not None and std is not None:
      try:
        p = float(prob)
        s = float(std)
        if np.isfinite(p) and np.isfinite(s) and _MIN_LANE_PROB <= p <= 1.0 and 0.0 <= s <= _MAX_LANE_STD:
          x = np.asarray(lane_line.x, dtype=float)
          y = np.asarray(lane_line.y, dtype=float)
          if self._valid_path(x, y) and self._covers(x, lookahead):
            return x, y
      except (AttributeError, IndexError, TypeError, ValueError):
        pass

    # Fall back to road edge when lane line is absent or uncertain
    if road_edge is not None and road_edge_std is not None:
      try:
        s = float(road_edge_std)
        if np.isfinite(s) and 0.0 <= s <= _MAX_ROAD_EDGE_STD:
          x = np.asarray(road_edge.x, dtype=float)
          y = np.asarray(road_edge.y, dtype=float)
          if self._valid_path(x, y) and self._covers(x, lookahead):
            return x, y
      except (AttributeError, IndexError, TypeError, ValueError):
        pass

    return None, None

  def _raw_correction(self, model_v2, v_ego: float, offset: float, e2e_authority: float) -> tuple[bool, float]:
    try:
      lookahead = float(np.clip(v_ego, 8.0, 35.0))
      pos_x = np.asarray(model_v2.position.x, dtype=float)
      pos_y = np.asarray(model_v2.position.y, dtype=float)
      if not (self._valid_path(pos_x, pos_y) and self._covers(pos_x, lookahead)):
        return False, 0.0

      lane_lines = getattr(model_v2, "laneLines", [])
      probs = np.asarray(getattr(model_v2, "laneLineProbs", []), dtype=float)
      stds = np.asarray(getattr(model_v2, "laneLineStds", []), dtype=float)

      road_edges = getattr(model_v2, "roadEdges", [])
      road_edge_stds = np.asarray(getattr(model_v2, "roadEdgeStds", []), dtype=float)

      left_ll = lane_lines[1] if len(lane_lines) > 1 else None
      left_prob = probs[1] if probs.size > 1 else None
      left_std = stds[1] if stds.size > 1 else None
      left_re = road_edges[0] if len(road_edges) > 0 else None
      left_re_std = road_edge_stds[0] if road_edge_stds.size > 0 else None

      left_x, left_y = self._get_boundary(left_ll, left_prob, left_std, left_re, left_re_std, lookahead)
      if left_x is None or left_y is None:
        return False, 0.0

      right_ll = lane_lines[2] if len(lane_lines) > 2 else None
      right_prob = probs[2] if probs.size > 2 else None
      right_std = stds[2] if stds.size > 2 else None
      right_re = road_edges[1] if len(road_edges) > 1 else None
      right_re_std = road_edge_stds[1] if road_edge_stds.size > 1 else None

      right_x, right_y = self._get_boundary(right_ll, right_prob, right_std, right_re, right_re_std, lookahead)
      if right_x is None or right_y is None:
        return False, 0.0

      left = float(np.interp(lookahead, left_x, left_y))
      right = float(np.interp(lookahead, right_x, right_y))
      width = right - left
      if not _MIN_LANE_WIDTH <= width <= _MAX_LANE_WIDTH:
        return False, 0.0

      max_safe_offset = min(_MAX_OFFSET, max(0.0, width * 0.5 - _MIN_CENTER_TO_LINE))
      target_y = 0.5 * (left + right) + float(np.clip(offset, -max_safe_offset, max_safe_offset))
      model_y = float(np.interp(lookahead, pos_x, pos_y))
      error = target_y - model_y
      error_abs = abs(error)
      if error_abs <= _CENTER_ERROR_DEADBAND:
        error = 0.0
      else:
        error = np.copysign(error_abs - _CENTER_ERROR_DEADBAND, error)

      try:
        pos_y_std = np.asarray(model_v2.position.yStd, dtype=float)
        if self._valid_path(pos_x, pos_y_std):
          path_std = float(np.interp(lookahead, pos_x, pos_y_std))
          if 0.0 <= path_std <= _E2E_MAX_PATH_STD:
            break_in = np.clip(
              (error_abs - _E2E_BREAK_IN_START) / (_E2E_BREAK_IN_FULL - _E2E_BREAK_IN_START),
              0.0,
              1.0,
            )
            error *= 1.0 - e2e_authority * float(break_in)
      except (AttributeError, TypeError, ValueError):
        pass

      return True, float(2.0 * error / lookahead ** 2)
    except (AttributeError, IndexError, TypeError, ValueError):
      return False, 0.0
