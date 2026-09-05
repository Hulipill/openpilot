"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
from collections.abc import Callable
import pyray as rl

from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.sunnypilot.widgets.list_view import toggle_item_sp, option_item_sp, LineSeparatorSP
from openpilot.system.ui.widgets.network import NavButton
from openpilot.system.ui.widgets.scroller_tici import Scroller
from openpilot.system.ui.widgets import Widget


class LaneCenteringSettingsLayout(Widget):
  def __init__(self, back_btn_callback: Callable):
    super().__init__()
    self._back_button = NavButton(tr("Back"))
    self._back_button.set_click_callback(back_btn_callback)

    items = self._initialize_items()
    self._scroller = Scroller(items, line_separator=False, spacing=0)

  def _initialize_items(self):
    self._lane_center_offset = option_item_sp(
      title=lambda: tr("Lane Center Offset"),
      param="LaneCenterOffset",
      description=lambda: tr("Shift the lane target left or right in meters. The controller reduces this offset automatically when the detected lane is narrow."),
      min_value=-30,
      max_value=30,
      value_change_step=1,
      use_float_scaling=True,
      label_callback=lambda x: f"{x / 100:.2f} m",
    )
    self._pause_on_signal = toggle_item_sp(
      param="LaneCenteringPauseOnSignal",
      title=lambda: tr("Pause Lane Centering On Turn Signal"),
      description=lambda: tr("Fade lane-centering correction out when a turn signal is active so it does not fight a lane change or turn."),
    )
    self._e2e_authority = option_item_sp(
      title=lambda: tr("E2E Override Strength"),
      param="LaneCenteringE2EAuthority",
      description=lambda: tr("Choose how strongly the vision model may override lane centering when it sees a hazard."),
      min_value=0,
      max_value=100,
      value_change_step=5,
      use_float_scaling=True,
      label_callback=lambda x: f"{x / 100:.2f}",
    )

    items = [
      self._lane_center_offset,
      LineSeparatorSP(40),
      self._pause_on_signal,
      LineSeparatorSP(40),
      self._e2e_authority,
    ]

    return items

  def _update_state(self):
    super()._update_state()

  def _render(self, rect):
    self._back_button.set_position(self._rect.x, self._rect.y + 20)
    self._back_button.render()
    content_rect = rl.Rectangle(rect.x, rect.y + self._back_button.rect.height + 40, rect.width, rect.height - self._back_button.rect.height - 40)
    self._scroller.render(content_rect)

  def show_event(self):
    self._scroller.show_event()
