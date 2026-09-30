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


from collections.abc import Sequence

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from spyc.assist.targets import Target
from spyc.core.printable import printable


# Asks what to describe when the cursor is in code: the smallest thing first, and chosen at once by Enter.
class ScopeMenu(ModalScreen[Target | None]):
    DEFAULT_CSS = """
    ScopeMenu { align: center middle; }
    ScopeMenu > Vertical { width: 60; max-width: 95%; height: auto; border: round $accent; background: $surface; }
    ScopeMenu OptionList { height: auto; max-height: 10; border: none; background: transparent; }
    """
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, targets: Sequence[Target]) -> None:
        super().__init__()
        self._targets = tuple(targets)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Ask Claude about")
            yield OptionList(*(Option(printable(f"{target.kind} {target.label}")) for target in self._targets))

    def on_mount(self) -> None:
        options = self.query_one(OptionList)
        options.highlighted = 0
        options.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(self._targets[event.option_index])

    def action_cancel(self) -> None:
        self.dismiss(None)
