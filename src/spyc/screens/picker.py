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


from rich.text import Text
from textual import events, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
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
    Picker #picker-status { height: 1; padding: 0 1; color: $text-muted; }
    Picker Horizontal { height: 1fr; }
    Picker OptionList { width: 45%; border: none; background: transparent; text-wrap: nowrap; text-overflow: ellipsis; }
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
        Binding("alt+r,ctrl+r", "toggle_regex", show=False),
        Binding("alt+w", "toggle_word", show=False),
    ]

    def __init__(self, source: PickerSource, initial: str = "") -> None:
        super().__init__()
        self._source, self._initial = source, initial
        self._items: list[Item] = []
        self._preview_timer = None
        self._search_timer = None
        self._generation = 0

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Input(self._initial, placeholder=self._source.placeholder)
            yield Static(id="picker-status")
            with Horizontal():
                yield OptionList()
                yield CodeView()

    def on_mount(self) -> None:
        self.query_one(CodeView).can_focus = False
        self.set_class(self.app.size.width < NARROW_WIDTH, "-narrow")
        self._search_now(self._initial)

    def on_resize(self, event: events.Resize) -> None:
        self.set_class(event.size.width < NARROW_WIDTH, "-narrow")

    # A source that searches many files says so with `threaded`, and is then
    # asked from a worker thread, once typing has paused for `debounce`
    # seconds; an answer that arrives after a newer question is dropped.
    def on_input_changed(self, event: Input.Changed) -> None:
        if self._search_timer is not None:
            self._search_timer.stop()
        pause = getattr(self._source, "debounce", 0.0)
        if pause:
            self._search_timer = self.set_timer(pause, lambda: self._search_now(event.value))
        else:
            self._search_now(event.value)

    def _search_now(self, query: str) -> None:
        if getattr(self._source, "threaded", False):
            self._generation += 1
            self._ask(self._generation, query)
        else:
            self._show(self._source.search(query))

    @work(thread=True, group="picker-search", exit_on_error=False)
    def _ask(self, generation: int, query: str) -> None:
        self.app.call_from_thread(self._answered, generation, self._source.search(query))

    def _answered(self, generation: int, items: list[Item]) -> None:
        if generation == self._generation:
            self._show(items)

    def _show(self, items: list[Item]) -> None:
        self._items = items
        options = self.query_one(OptionList)
        options.clear_options()
        options.add_options([Option(item.label) for item in items])
        options.highlighted = 0 if items else None
        self._show_status()

    def _show_status(self) -> None:
        mode, summary = getattr(self._source, "mode_text", None), getattr(self._source, "summary", None)
        text = "  ".join(part for part in (mode and mode(), summary and summary()) if part)
        status = self.query_one("#picker-status", Static)
        status.display = bool(text)
        status.update(Text(text))

    def action_toggle_regex(self) -> None:
        self._toggle("toggle_regex")

    def action_toggle_word(self) -> None:
        self._toggle("toggle_word")

    def _toggle(self, name: str) -> None:
        toggle = getattr(self._source, name, None)
        if toggle is not None:
            toggle()
            self._search_now(self.query_one(Input).value)

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
