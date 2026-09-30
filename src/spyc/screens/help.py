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
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

# (keys, app action or None, description). The action ties a row to a binding
# of SpycApp, and a test fails when a binding has no row.
HELP_ROWS: list[tuple[str, str | None, str]] = [
    ("f", "find_file", "Find a file by name; name:line jumps to a line"),
    ("s", "search_project", "Search the text of the project; alt+r or F2 switches to a pattern, alt+w or F3 to whole words"),
    ("o", "show_outline", "Outline: the definitions of this file"),
    ("t", "find_symbol", "Find a definition anywhere in the project"),
    ("d", "go_to_definition", "Go to the definition of the name under the cursor; [ comes back"),
    ("/", "search_in_file", "Find in the file; n and N step through the matches"),
    (":", "goto_line", "Go to a line"),
    ("[  ]", "history_back", "Back through the files you have visited"),
    ("", "history_forward", "Forward again"),
    ("l", "show_log", "Commit log; the diff of each commit beside it, Enter on a line opens it"),
    ("L", "show_file_log", "History of the open file"),
    ("g", "show_changes", "All uncommitted changes as one diff"),
    ("b", "toggle_blame", "Show who last changed each line; Enter on a line opens that commit"),
    ("c", "toggle_coverage", "Show or hide what the tests ran; reports are found by name or given with --coverage"),
    ("G", "show_graph", "Dependency graph: packages (Java, Kotlin) or directories, files and classes; [ ] change level, c cycles"),
    ("a", "about", "Ask Claude to describe the directory, package, file or class; needs claude installed and logged in"),
    ("e", "edit", "Edit in $VISUAL or $EDITOR at the cursor line"),
    ("p", "copy_location", "Copy path:line to the clipboard"),
    ("i", "overview", "Project overview"),
    ("\\", "toggle_sidebar", "Show or hide the file tree"),
    (".", "toggle_ignored", "Show or hide files that git ignores"),
    ("R", "refresh_project", "Read the file list again"),
    ("r", "toggle_markdown", "Rendered or source view of a Markdown file"),
    ("Tab", None, "Switch between the tree and the code; in the log, between the commits and the diff"),
    ("n  N", None, "In a diff, the next or previous file; in the log, / filters by message and R reads the changes again"),
    ("?", "help", "This help"),
    ("q", "quit", "Quit"),
    ("↑ ↓ j k", None, "Move by line; ← → move by character"),
    ("Home End", None, "Start or end of the line"),
    ("PgUp PgDn Space", None, "Move by page; ctrl+u and ctrl+d move by half a page"),
    ("ctrl+Home ctrl+End", None, "Start or end of the file"),
    ("Enter", None, "Open the file in the tree; ← and → close and open directories"),
    ("ctrl+p", None, "Command palette, where the color theme can be changed"),
]


def help_text() -> Text:
    text = Text()
    for keys, _, description in HELP_ROWS:
        text.append(f"{keys:<20}", style="bold")
        text.append(f"{description}\n")
    return text


class HelpScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    HelpScreen { align: center middle; }
    HelpScreen > VerticalScroll { width: 84; max-width: 95%; height: auto; max-height: 90%; padding: 1 2;
                                  border: round $accent; background: $surface; }
    """
    BINDINGS = [Binding("escape,question_mark,q", "close", "Close")]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(help_text())

    def action_close(self) -> None:
        self.dismiss(None)
