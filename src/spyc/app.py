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


import subprocess
import time
from pathlib import Path

from textual import work
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Footer, Header, OptionList
from textual.worker import Worker, WorkerState

from spyc.document import load_document
from spyc.editor import editor_command
from spyc.file_index import MAX_INDEXED_FILES, FileIndex, build_index
from spyc.file_picker import FilePickerSource
from spyc.fuzzy import PathMatcher
from spyc.git.blame import BlameLine
from spyc.git.changes import LineChanges
from spyc.git.repository import Git
from spyc.git.status import rollup
from spyc.git.summary import GitSummary
from spyc.history import JumpHistory, Place
from spyc.location import Location
from spyc.overview import Overview, build_overview
from spyc.picking import Choice
from spyc.printable import printable
from spyc.screens.changes import ChangesScreen
from spyc.screens.help import HelpScreen
from spyc.screens.log import LogScreen
from spyc.screens.picker import Picker
from spyc.screens.prompt import Prompt
from spyc.state import StateStore
from spyc.tree_model import TreeModel
from spyc.widgets.code_view import CodeView
from spyc.widgets.file_tree import FileTree
from spyc.widgets.markdown_pane import MarkdownPane
from spyc.widgets.overview_pane import OverviewPane
from spyc.widgets.status_bar import StatusBar

RELOAD_INTERVAL = 2.0
GIT_INTERVAL = 10.0
SLOW_GIT_SECONDS = 2.0
MARKDOWN_LIMIT = 50_000
# Keys that act on the main view, which is hidden behind the log, the changes
# and the pickers while those are open.
MAIN_VIEW_ACTIONS = frozenset({
    "find_file", "search_in_file", "goto_line", "history_back", "history_forward", "show_log", "show_file_log",
    "show_changes", "toggle_blame", "edit", "copy_location", "overview", "toggle_sidebar", "toggle_ignored",
    "toggle_markdown", "refresh_project"})


class SpycApp(App):
    TITLE = "spyc"
    CSS = """
    #tree { width: 34; border-right: solid $primary; }
    #main { width: 1fr; }
    #overview, #code { height: 1fr; }
    """
    BINDINGS = [
        Binding("f", "find_file", "Find file"),
        Binding("slash", "search_in_file", "Find in file"),
        Binding("colon", "goto_line", "Go to line"),
        Binding("left_square_bracket", "history_back", "Back", show=False),
        Binding("right_square_bracket", "history_forward", "Forward", show=False),
        Binding("l", "show_log", "Log"),
        Binding("L", "show_file_log", "File log", show=False),
        Binding("g", "show_changes", "Changes"),
        Binding("b", "toggle_blame", "Blame"),
        Binding("e", "edit", "Edit"),
        Binding("p", "copy_location", "Copy path", show=False),
        Binding("i", "overview", "Overview"),
        Binding("backslash", "toggle_sidebar", "Sidebar", show=False),
        Binding("full_stop", "toggle_ignored", "Ignored", show=False),
        Binding("r", "toggle_markdown", "Rendered", show=False),
        Binding("R", "refresh_project", "Refresh", show=False),
        Binding("question_mark", "help", "Help"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, project_root: Path, start: Location | None = None, store: StateStore | None = None,
                 max_files: int = MAX_INDEXED_FILES) -> None:
        super().__init__()
        self.project_root = project_root
        self.store = store or StateStore()
        self.history = JumpHistory()
        self.overview: Overview | None = None
        self.git = Git(project_root)
        self.git_enabled = True
        self._git_seen = False
        self._git_slow = False
        self._git_files: dict[str, str] = {}
        self._blame_on = False
        self._start_location = start
        self._max_files = max_files
        self._matcher: PathMatcher | None = None
        self._show_ignored = False
        self._index_generation = 0
        self._last_query = ""

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        return not (action in MAIN_VIEW_ACTIONS and len(self.screen_stack) > 1)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield FileTree(id="tree")
            with Vertical(id="main"):
                yield OverviewPane(id="overview")
                yield CodeView(id="code")
                yield MarkdownPane(id="rendered")
                yield StatusBar()
        yield Footer()

    # Pickers and prompts are screens stacked on this one, and a query on the
    # app searches the topmost screen, so the main widgets are looked up on the
    # bottom one. Result callbacks can run while a modal is still on top.
    @property
    def _tree(self) -> FileTree:
        return self.screen_stack[0].query_one(FileTree)

    @property
    def _code(self) -> CodeView:
        return self.screen_stack[0].query_one(CodeView)

    @property
    def _overview_pane(self) -> OverviewPane:
        return self.screen_stack[0].query_one(OverviewPane)

    @property
    def _status(self) -> StatusBar:
        return self.screen_stack[0].query_one(StatusBar)

    @property
    def _rendered(self) -> MarkdownPane:
        return self.screen_stack[0].query_one(MarkdownPane)

    def on_mount(self) -> None:
        saved_theme = self.store.get("theme")
        if saved_theme in self.available_themes:
            self.theme = saved_theme
        self.theme_changed_signal.subscribe(self, lambda theme: self.store.set("theme", theme.name))
        self.sub_title = printable(str(self.project_root))
        self._code.display = False
        self._rendered.display = False
        self._tree.display = bool(self.store.get("sidebar", True))
        self.set_interval(RELOAD_INTERVAL, self._check_for_changes)
        self.set_interval(GIT_INTERVAL, self._poll_git)
        self._reload_index()
        self._refresh_git()
        start = self._start_location
        if start is not None and (self.project_root / start.path).is_file():
            self.open_file(start.path, start.line)
        else:
            self._tree.focus()

    # The index is built off the UI thread: a large tree takes seconds, and the
    # window must be usable, and a file openable, while it is read.
    # A thread cannot be stopped once it runs, so an index that was replaced by
    # a newer request is recognised by its generation and dropped when it lands.
    def _reload_index(self) -> None:
        self._index_generation += 1
        self._load_index(self._index_generation, self._show_ignored)

    @work(thread=True, exclusive=True, group="index", exit_on_error=False)
    def _load_index(self, generation: int, show_ignored: bool) -> None:
        index = build_index(self.project_root, show_ignored, self._max_files)
        self.call_from_thread(self._index_ready, generation, index, TreeModel(index.paths), build_overview(index),
                              PathMatcher(index.paths))

    def _index_ready(self, generation: int, index: FileIndex, model: TreeModel, overview: Overview,
                     matcher: PathMatcher) -> None:
        if generation != self._index_generation:
            return
        self.overview, self._matcher = overview, matcher
        self._tree.load(model)
        self._overview_pane.show(overview)
        if index.truncated:
            self.notify(f"Only the first {len(index.paths):,} files are listed", severity="warning")
        code = self._code
        start = self._start_location
        focus = code.display_path if code.document is not None else (start.path if start else "")
        if focus:
            self._tree.reveal(focus)

    # Git is asked again on a timer, when the window regains focus, after the
    # editor and on request, and not at all once it is clear that this is not a
    # repository. A repository that takes seconds to answer is left alone by
    # the timer, which would otherwise keep it busy for good.
    def _poll_git(self) -> None:
        if not self._git_slow:
            self._refresh_git()

    def _refresh_git(self) -> None:
        if self.git_enabled:
            self._load_git_status()

    @work(thread=True, exclusive=True, group="git-status", exit_on_error=False)
    def _load_git_status(self) -> None:
        started = time.monotonic()
        status = self.git.status()
        summary = None if status is None else self.git.summary(status)
        directories = None if status is None else rollup(status)
        slow = time.monotonic() - started > SLOW_GIT_SECONDS
        self.call_from_thread(self._git_status_ready, status, summary, directories, slow)

    def _git_status_ready(self, status: dict[str, str] | None, summary: GitSummary | None,
                          directories: dict[str, str] | None, slow: bool) -> None:
        self._git_slow = slow
        if status is None:
            self.git_enabled = self._git_seen
            return
        changed = not self._git_seen or status != self._git_files
        self._git_seen, self._git_files = True, status
        self._overview_pane.show_git(summary)
        if summary and summary.branch:
            self.sub_title = printable(f"{self.project_root}  ⎇ {summary.branch}")
        if changed:
            self._tree.set_status(status, directories)
            self._refresh_changes()
            self._refresh_blame()

    # The column of marks is reserved the moment a file is shown, and filled
    # in when git has answered.
    def _refresh_changes(self) -> None:
        code = self._code
        if not (self.git_enabled and self._git_seen) or code.document is None:
            return
        if code.changes is None:
            code.set_changes(LineChanges())
        path = code.display_path
        self._load_changes(path, len(code.document.lines), self._git_files.get(path) == "?")

    @work(thread=True, exclusive=True, group="git-changes", exit_on_error=False)
    def _load_changes(self, path: str, line_count: int, untracked: bool) -> None:
        changes = LineChanges.everything(line_count) if untracked else self.git.line_changes(path)
        self.call_from_thread(self._changes_ready, path, changes)

    def _changes_ready(self, path: str, changes: LineChanges | None) -> None:
        code = self._code
        if changes is not None and code.display_path == path:
            code.set_changes(changes)

    def on_app_focus(self, event: events.AppFocus) -> None:
        self._refresh_git()

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state is WorkerState.ERROR and event.worker.group == "index":
            self.notify(f"Could not read the project files: {event.worker.error}", severity="error", markup=False)

    def open_file(self, path: str, line: int | None = None) -> None:
        leaving = self._current_place()
        if self._display_file(path, line):
            self.history.navigate(leaving, Place(path, line or 1))

    def _display_file(self, path: str, line: int | None) -> bool:
        try:
            document = load_document(self.project_root / path)
        except OSError as error:
            self.notify(f"Cannot open {printable(path)}: {error.strerror or error}", severity="error", markup=False)
            return False
        code = self._code
        code.show(document, path)
        self._overview_pane.display = False
        self._rendered.display = False
        code.display = True
        if line:
            self.call_after_refresh(code.goto, line)
        self.store.add_recent_file(self.project_root, path)
        self._tree.reveal(path)
        code.focus()
        self._refresh_changes()
        self._refresh_blame()
        return True

    def _current_place(self) -> Place | None:
        code = self._code
        return Place(code.display_path, code.cursor_row + 1) if code.document is not None else None

    def _viewing(self) -> CodeView | None:
        code = self._code
        return code if code.display and code.document is not None else None

    def on_file_tree_file_chosen(self, message: FileTree.FileChosen) -> None:
        self.open_file(message.path)

    def on_code_view_cursor_moved(self, message: CodeView.CursorMoved) -> None:
        self._refresh_status()

    def _refresh_status(self) -> None:
        code = self._code
        document = code.document
        if document is not None:
            language = document.language.name if document.language else None
            self._status.show(code.display_path, language, code.cursor_row, code.cursor_column,
                              len(document.lines), code.match_status)

    def action_find_file(self) -> None:
        if self._matcher is None:
            self.notify("Still reading the project files")
            return
        source = FilePickerSource(self.project_root, self._matcher, lambda: self.store.recent_files(self.project_root))
        self.push_screen(Picker(source), self._file_chosen)

    def _file_chosen(self, choice: Choice | None) -> None:
        if choice is not None:
            self.open_file(choice.key, choice.line)

    def action_search_in_file(self) -> None:
        if self._viewing() is not None:
            self.push_screen(Prompt("Find in file", self._last_query), self._searched)

    def _searched(self, query: str | None) -> None:
        code = self._viewing()
        if query is None or code is None:
            return
        self._last_query = query
        if not query:
            code.clear_search()
        elif code.search(query) == 0:
            self.notify(f"No matches for {printable(query)!r}", severity="warning", markup=False)
        self._refresh_status()

    def action_goto_line(self) -> None:
        if self._viewing() is not None:
            self.push_screen(Prompt("Go to line", restrict=r"[0-9]*"), self._went_to)

    def _went_to(self, value: str | None) -> None:
        code = self._viewing()
        if value and code is not None:
            code.goto(int(value))

    def _in_git(self) -> bool:
        if not self.git_enabled:
            self.notify("Not a git repository")
        return self.git_enabled

    def action_show_log(self) -> None:
        if self._in_git():
            self.push_screen(LogScreen(self.git), self._location_chosen)

    def action_show_file_log(self) -> None:
        if not self._in_git():
            return
        code = self._code
        if code.document is None:
            self.notify("Open a file to see its history")
            return
        self.push_screen(LogScreen(self.git, code.display_path), self._location_chosen)

    def action_show_changes(self) -> None:
        if self._in_git():
            self.push_screen(ChangesScreen(self.git, self._untracked_files), self._location_chosen)

    def action_toggle_blame(self) -> None:
        code = self._viewing()
        if code is None or not self._in_git():
            return
        self._blame_on = not self._blame_on
        if self._blame_on:
            self._refresh_blame()
        else:
            code.set_blame(None)

    # Like the change marks, the column is reserved at once and filled when
    # git has answered; a file git does not know keeps a blank column.
    def _refresh_blame(self) -> None:
        code = self._code
        if not self._blame_on or code.document is None:
            return
        if code.blame is None:
            code.set_blame([])
        self._load_blame(code.display_path)

    @work(thread=True, exclusive=True, group="git-blame", exit_on_error=False)
    def _load_blame(self, path: str) -> None:
        self.call_from_thread(self._blame_ready, path, self.git.blame(path))

    def _blame_ready(self, path: str, lines: list[BlameLine] | None) -> None:
        code = self._code
        if self._blame_on and lines is not None and code.display_path == path:
            code.set_blame(lines)

    def on_code_view_open_commit(self, message: CodeView.OpenCommit) -> None:
        if message.hash is None:
            self.action_show_changes()
        else:
            self.push_screen(LogScreen(self.git, focus=message.hash), self._location_chosen)

    def _untracked_files(self) -> list[str]:
        return [path for path, code in self._git_files.items() if code == "?"]

    def _location_chosen(self, location: Location | None) -> None:
        if location is not None:
            self.open_file(location.path, location.line)

    def action_history_back(self) -> None:
        self._step(self.history.back)

    def action_history_forward(self) -> None:
        self._step(self.history.forward)

    def _step(self, move) -> None:
        current = self._current_place()
        destination = move(current) if current is not None else None
        if destination is not None:
            self._display_file(destination.path, destination.line)

    async def action_edit(self) -> None:
        code = self._viewing()
        if code is None:
            return
        command = editor_command(self.project_root / code.display_path, code.cursor_row + 1)
        if command is None:
            self.notify("Set $VISUAL or $EDITOR to edit files", severity="warning", markup=False)
            return
        error = self._run_editor(command)
        if error is not None:
            self.notify(f"Could not start the editor: {error}", severity="error", markup=False)
        await self._check_for_changes()
        self._refresh_git()

    # A stat every couple of seconds needs no dependency and works on network mounts, unlike inotify.
    async def _check_for_changes(self) -> None:
        document = self._code.document
        if document is None:
            return
        try:
            changed = document.path.stat().st_mtime != document.mtime
        except OSError:
            return
        if changed:
            await self._reload()

    async def _reload(self) -> None:
        code = self._code
        try:
            document = load_document(code.document.path)
        except OSError:
            return
        code.replace(document)
        self._refresh_git()
        self._refresh_blame()
        if self._rendered.display:
            if len(document.text) > MARKDOWN_LIMIT:
                self._rendered.display, code.display = False, True
            else:
                await self._rendered.show(document.text)
        self._refresh_status()

    # Asking for a refresh also gives git another chance: it may have failed
    # once on a slow disk, or the folder may have become a repository since.
    def action_refresh_project(self) -> None:
        self.git_enabled = True
        self._reload_index()
        self._refresh_git()

    async def action_toggle_markdown(self) -> None:
        rendered, code = self._rendered, self._code
        if rendered.display:
            rendered.display, code.display = False, True
            code.focus()
            return
        document = code.document if code.display else None
        if document is None or document.language is None or document.language.id != "markdown":
            self.notify("Only Markdown files can be rendered")
            return
        if len(document.text) > MARKDOWN_LIMIT:
            self.notify("Too large to render; showing the source", severity="warning")
            return
        await rendered.show(document.text)
        code.display, rendered.display = False, True
        rendered.focus()

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    # A command that cannot start must come back as a message: an exception
    # inside suspend() would leave the terminal without the application mode.
    def _run_editor(self, command: list[str]) -> str | None:
        with self.suspend():
            try:
                subprocess.run(command, check=False)
            except OSError as error:
                return str(error)
        return None

    def action_copy_location(self) -> None:
        code = self._viewing()
        if code is not None:
            location = f"{code.display_path}:{code.cursor_row + 1}"
            self.copy_to_clipboard(location)
            self.notify(f"Copied {printable(location)}", markup=False)

    def action_overview(self) -> None:
        self._code.display = False
        self._rendered.display = False
        self._overview_pane.display = True
        self._tree.focus()

    def action_toggle_sidebar(self) -> None:
        tree = self._tree
        tree.display = not tree.display
        self.store.set("sidebar", tree.display)

    def action_toggle_ignored(self) -> None:
        self._show_ignored = not self._show_ignored
        self.notify("Showing ignored files" if self._show_ignored else "Hiding ignored files")
        self._reload_index()

    # Every screen binds Tab to app.focus_next, which is what runs before any
    # app-level key binding could, so the pane switch replaces that action.
    # Inside a picker or prompt Tab keeps its normal meaning.
    def action_focus_next(self) -> None:
        if len(self.screen_stack) > 1:
            super().action_focus_next()
        else:
            self._switch_pane()

    def action_focus_previous(self) -> None:
        if len(self.screen_stack) > 1:
            super().action_focus_previous()
        else:
            self._switch_pane()

    def _switch_pane(self) -> None:
        tree, main = self._tree, self._main_pane()
        (main if tree.has_focus or not tree.display else tree).focus()

    def _main_pane(self) -> Widget:
        if self._code.display:
            return self._code
        if self._rendered.display:
            return self._rendered
        key_files = self._overview_pane.query_one("#key-files", OptionList)
        return key_files if key_files.display else self._overview_pane
