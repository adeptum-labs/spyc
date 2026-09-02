# spyc is a terminal viewer for browsing code bases.
# Copyright © 2026 Adam Waldenberg, Adeptum AB, Org.nr 559494-1824.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>.
#
# Website: https://www.adeptum.se
# Contact: info@adeptum.se


from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option

from spyc.picking import Choice, Item, PickerSource
from spyc.widgets.code_view import CodeView

PREVIEW_DELAY = 0.1
NARROW_WIDTH = 100


class Picker(ModalScreen[Choice | None]):
    DEFAULT_CSS = """
    Picker { align: center middle; }
    Picker > Vertical { width: 92%; height: 85%; border: round $accent; background: $surface; }
    Picker Input { border: none; border-bottom: solid $primary; }
    Picker Horizontal { height: 1fr; }
    Picker OptionList { width: 45%; border: none; background: transparent; }
    Picker CodeView { width: 55%; border-left: solid $primary; }
    Picker.-narrow OptionList { width: 100%; }
    Picker.-narrow CodeView { display: none; }
    """
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("down", "move(1)", show=False),
        Binding("up", "move(-1)", show=False),
        Binding("pagedown", "move(10)", show=False),
        Binding("pageup", "move(-10)", show=False),
    ]

    def __init__(self, source: PickerSource) -> None:
        super().__init__()
        self._source = source
        self._items: list[Item] = []
        self._preview_timer = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Input(placeholder=self._source.placeholder)
            with Horizontal():
                yield OptionList()
                yield CodeView()

    def on_mount(self) -> None:
        self.query_one(CodeView).can_focus = False
        self.set_class(self.app.size.width < NARROW_WIDTH, "-narrow")
        self._search("")

    def on_resize(self, event: events.Resize) -> None:
        self.set_class(event.size.width < NARROW_WIDTH, "-narrow")

    def on_input_changed(self, event: Input.Changed) -> None:
        self._search(event.value)

    def _search(self, query: str) -> None:
        self._items = self._source.search(query)
        options = self.query_one(OptionList)
        options.clear_options()
        options.add_options([Option(item.label) for item in self._items])
        options.highlighted = 0 if self._items else None

    # The preview is debounced so holding Down through a long list loads one
    # file, not fifty.
    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if self._preview_timer is not None:
            self._preview_timer.stop()
        self._preview_timer = self.set_timer(PREVIEW_DELAY, lambda: self._preview(event.option_index))

    def _preview(self, index: int) -> None:
        if not 0 <= index < len(self._items):
            return
        item = self._items[index]
        document = self._source.preview(item)
        if document is None:
            return
        view = self.query_one(CodeView)
        view.show(document, item.key)
        if item.line:
            view.goto(item.line)

    # The preview has its own cursor; the main screen's status bar must not see it.
    def on_code_view_cursor_moved(self, event: CodeView.CursorMoved) -> None:
        event.stop()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._choose(self.query_one(OptionList).highlighted)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self._choose(event.option_index)

    def _choose(self, index: int | None) -> None:
        if index is not None and 0 <= index < len(self._items):
            item = self._items[index]
            self.dismiss(Choice(item.key, item.line))

    def action_move(self, delta: int) -> None:
        if self._items:
            options = self.query_one(OptionList)
            options.highlighted = min(max((options.highlighted or 0) + delta, 0), len(self._items) - 1)

    def action_cancel(self) -> None:
        self.dismiss(None)
