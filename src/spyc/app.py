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
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from textual import work
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Footer, Header, OptionList
from textual.worker import Worker, WorkerState, get_current_worker

from spyc.about import About
from spyc.assist.cache import AnswerCache
from spyc.assist.cli import Claude, find_claude
from spyc.assist.targets import Target
from spyc.core.cache_files import cache_path
from spyc.core.document import load_document
from spyc.core.file_index import MAX_INDEXED_FILES, FileIndex
from spyc.core.file_picker import FilePickerSource
from spyc.core.fuzzy import PathMatcher
from spyc.core.languages import detect_language
from spyc.core.location import Location
from spyc.core.overview import Overview, build_overview
from spyc.core.picking import Choice
from spyc.core.printable import printable
from spyc.core.source import DiskSource, FileSource
from spyc.core.tree_model import TreeModel
from spyc.coverage.index import Coverage
from spyc.coverage.reports import find_reports, load_reports
from spyc.coverage.text import coverage_status
from spyc.deps.graph import DependencyGraph, Stopped
from spyc.deps.scopes import Member
from spyc.editor import editor_command
from spyc.git.blame import BlameLine
from spyc.git.branches import Branch
from spyc.git.changes import LineChanges
from spyc.git.ref_source import GitRefSource
from spyc.git.repository import Git
from spyc.git.status import rollup
from spyc.git.summary import GitSummary
from spyc.history import JumpHistory, Place
from spyc.screens.branches import BranchesScreen, BranchPick
from spyc.screens.changes import ChangesScreen
from spyc.screens.explain import ExplainScreen
from spyc.screens.graph import GraphScreen
from spyc.screens.help import HelpScreen
from spyc.screens.log import LogScreen
from spyc.screens.picker import Picker
from spyc.screens.prompt import Prompt
from spyc.screens.scope_menu import ScopeMenu
from spyc.search_picker import SearchSource
from spyc.state import StateStore
from spyc.symbol_index import Located, SymbolIndex, default_cache_path, ref_cache_path
from spyc.symbol_picker import LIST_LIMIT, SymbolSource
from spyc.symbols import Symbol, symbols_of
from spyc.widgets.code_view import CodeView
from spyc.widgets.file_tree import FileTree
from spyc.widgets.markdown_pane import MarkdownPane
from spyc.widgets.overview_pane import OverviewPane
from spyc.widgets.splitter import Splitter
from spyc.widgets.status_bar import StatusBar

RELOAD_INTERVAL = 2.0
GIT_INTERVAL = 10.0
SLOW_GIT_SECONDS = 2.0
SIDEBAR_WIDTH = 34
SIDEBAR_STEP = 2
MIN_SIDEBAR_WIDTH = 12
MIN_MAIN_WIDTH = 20
MARKDOWN_LIMIT = 50_000
# Keys that act on the main view, which is hidden behind the log, the changes
# and the pickers while those are open.
MAIN_VIEW_ACTIONS = frozenset({
    "find_file", "search_project", "show_outline", "find_symbol", "go_to_definition", "search_in_file", "goto_line", "history_back", "history_forward", "show_log", "show_file_log",
    "show_branches", "show_changes", "toggle_blame", "toggle_coverage", "show_graph", "edit", "copy_location", "overview", "toggle_sidebar", "toggle_ignored",
    "toggle_markdown", "refresh_project", "about", "widen_sidebar", "narrow_sidebar"})


def _nearness(candidate: Located, current: str) -> tuple:
    place, here = PurePosixPath(candidate.path), PurePosixPath(current)
    return (place != here, place.parent != here.parent, place.suffix != here.suffix, candidate.path,
            candidate.symbol.line)


class SpycApp(App):
    TITLE = "spyc"
    CSS = """
    #tree { width: 34; }
    #main { width: 1fr; }
    #overview, #code { height: 1fr; }
    """
    BINDINGS = [
        Binding("question_mark", "help", "Help"),
        Binding("q", "quit", "Quit"),
        Binding("f", "find_file", "Open"),
        Binding("s", "search_project", "Search"),
        Binding("l", "show_log", "Log"),
        Binding("B", "show_branches", "Branches", show=False),
        Binding("o", "show_outline", "Outline"),
        Binding("slash", "search_in_file", "Find"),
        Binding("d", "go_to_definition", "Goto"),
        Binding("t", "find_symbol", "Symbols", show=False),
        Binding("colon", "goto_line", "Line", show=False),
        Binding("left_square_bracket", "history_back", "Back", show=False),
        Binding("right_square_bracket", "history_forward", "Forward", show=False),
        Binding("L", "show_file_log", "File log", show=False),
        Binding("g", "show_changes", "Changes", show=False),
        Binding("b", "toggle_blame", "Blame", show=False),
        Binding("c", "toggle_coverage", "Coverage", show=False),
        Binding("G", "show_graph", "Graph", show=False),
        Binding("a", "about", "About", show=False),
        Binding("e", "edit", "Edit", show=False),
        Binding("p", "copy_location", "Copy path", show=False),
        Binding("i", "overview", "Info", show=False),
        Binding("backslash", "toggle_sidebar", "Sidebar", show=False),
        Binding("greater_than_sign", "widen_sidebar", "Widen sidebar", show=False),
        Binding("less_than_sign", "narrow_sidebar", "Narrow sidebar", show=False),
        Binding("full_stop", "toggle_ignored", "Ignored", show=False),
        Binding("r", "toggle_markdown", "Rendered", show=False),
        Binding("R", "refresh_project", "Refresh", show=False),
    ]

    def __init__(self, project_root: Path, start: Location | None = None, store: StateStore | None = None,
                 max_files: int = MAX_INDEXED_FILES, coverage_files: Sequence[Path] = ()) -> None:
        super().__init__()
        self.project_root = project_root
        self.store = store or StateStore()
        self._coverage_files = tuple(coverage_files)
        self._coverage: Coverage | None = None
        self._coverage_loading = False
        self._graph: DependencyGraph | None = None
        self._graph_failure: str | None = None
        self._coverage_shown = bool(self.store.get("coverage", True))
        self._sidebar_width = int(self.store.get("sidebar_width", SIDEBAR_WIDTH))
        self.history = JumpHistory()
        self.overview: Overview | None = None
        self.git = Git(project_root)
        self.git_enabled = True
        self._git_seen = False
        self._git_slow = False
        self._git_summary: GitSummary | None = None
        self._open_after_listing: Location | None = None
        self._git_files: dict[str, str] = {}
        self._blame_on = False
        self._start_location = start
        self._max_files = max_files
        self._matcher: PathMatcher | None = None
        self._paths: tuple[str, ...] | None = None
        self._disk = DiskSource(project_root)
        self.source: FileSource = self._disk
        self._disk_symbols = SymbolIndex(project_root, default_cache_path(project_root), self._disk)
        self._symbols = self._disk_symbols
        self._about = About(self._symbols, lambda: self._paths, lambda: self._graph)
        self._answers = AnswerCache(cache_path(project_root, "claude"))
        self._claude: Claude | None = None
        self._show_ignored = False
        self._index_generation = 0
        self._last_query = ""

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "about" and (self._claude is None or not self.source.editable):
            return False
        return not (action in MAIN_VIEW_ACTIONS and len(self.screen_stack) > 1)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield FileTree(id="tree")
            yield Splitter(id="splitter")
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
        self._show_sidebar(bool(self.store.get("sidebar", True)))
        self._apply_sidebar_width()
        self.set_interval(RELOAD_INTERVAL, self._check_for_changes)
        self.set_interval(GIT_INTERVAL, self._poll_git)
        self._reload_index()
        self._refresh_git()
        self._look_for_claude()
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
        self._load_index(self._index_generation, self._show_ignored, self.source)

    @work(thread=True, exclusive=True, group="index", exit_on_error=False)
    def _load_index(self, generation: int, show_ignored: bool, source: FileSource) -> None:
        index = source.list_files(show_ignored, self._max_files)
        self.call_from_thread(self._index_ready, generation, index, TreeModel(index.paths), build_overview(index, source),
                              PathMatcher(index.paths))

    # The definitions and the facts for the graph are read in the background after
    # the files are known; a newer file list, or leaving the app, makes the running
    # pass stop, and the graph is built once a pass has run to its end.
    @work(thread=True, exclusive=True, group="symbols", exit_on_error=False)
    def _index_symbols(self, generation: int, paths: tuple[str, ...]) -> None:
        worker = get_current_worker()

        def stopped() -> bool:
            return worker.is_cancelled or generation != self._index_generation

        self._symbols.update(paths, stop=stopped)
        if stopped():
            return
        try:
            graph = DependencyGraph(self._symbols.facts(), stopped)
        except Stopped:
            return
        self.call_from_thread(self._graph_ready, generation, graph)

    def _graph_ready(self, generation: int, graph: DependencyGraph) -> None:
        if generation != self._index_generation:
            return
        self._graph, self._graph_failure = graph, None
        for screen in self.screen_stack:
            if isinstance(screen, GraphScreen):
                screen.set_graph(graph)

    def _graph_failed(self, error: object) -> None:
        self._graph_failure = f"Could not index the project: {printable(str(error))}"
        self.notify(self._graph_failure, severity="error", markup=False)
        for screen in self.screen_stack:
            if isinstance(screen, GraphScreen):
                screen.set_failure(self._graph_failure)

    def action_show_graph(self) -> None:
        code = self._code
        path = code.display_path if code.document is not None else None
        screen = GraphScreen(self.project_root, self._graph, self._symbol_progress, path, self._graph_failure,
                             self._explain_member if self._claude is not None and self.source.editable else None,
                             self.source)
        self.push_screen(screen, self._location_chosen)

    # Claude is used only when it is installed and logged in, which is asked once, without spending a request.
    @work(thread=True, exclusive=True, group="claude", exit_on_error=False)
    def _look_for_claude(self) -> None:
        self.call_from_thread(self._claude_found, find_claude())

    def _claude_found(self, claude: Claude | None) -> None:
        self._claude = claude
        self.refresh_bindings()

    def action_about(self) -> None:
        if self._paths is None:
            self.notify("Still reading the project files")
            return
        code = self._viewing()
        if code is not None and not self._tree.has_focus:
            scopes = self._about.scopes(code.display_path, code.document, code.cursor_row)
            self.push_screen(ScopeMenu(scopes), self._explain_chosen)
            return
        node = self._tree.cursor_node
        if node is None or node.data is None:
            self.notify("Select a file or directory first")
        else:
            self._explain(self._about.directory(node.data.path) if node.data.is_dir else self._about.file(node.data.path))

    def _explain_chosen(self, target: Target | None) -> None:
        if target is not None:
            self._explain(target)

    def _explain_member(self, member: Member, paths: tuple[str, ...]) -> None:
        self._explain(self._about.member(member.kind, member.key, paths))

    def _explain(self, target: Target) -> None:
        self.push_screen(ExplainScreen(self._claude, self._answers, self.project_root, target, self._about.facts_of))

    # The reports are those named on the command line, or else the ones the
    # project has; reading them can take a moment, so it is done off the UI thread.
    @work(thread=True, exclusive=True, group="coverage", exit_on_error=False)
    def _load_coverage(self, generation: int, paths: tuple[str, ...]) -> None:
        reports, errors = load_reports(self._coverage_files or find_reports(self.project_root))
        coverage = Coverage.build(self.project_root, paths, reports)
        self.call_from_thread(self._coverage_ready, generation, coverage, errors)

    def _coverage_ready(self, generation: int, coverage: Coverage, errors: list[str]) -> None:
        if generation != self._index_generation:
            return
        self._coverage_loading = False
        self._coverage = coverage if coverage.files else None
        if self._coverage_files:
            self._say_what_the_named_reports_gave(coverage, errors)
        self._apply_coverage()
        self._refresh_status()

    def _say_what_the_named_reports_gave(self, coverage: Coverage, errors: list[str]) -> None:
        for error in errors:
            self.notify(f"Coverage report skipped, {printable(error)}", severity="warning", markup=False)
        if not coverage.files:
            lost = coverage.unmatched
            detail = f" ({lost} file{'s were' if lost != 1 else ' was'} not found)" if lost else ""
            self.notify(f"No file of the project is in the coverage reports that were named{detail}", severity="warning")

    def _apply_coverage(self) -> None:
        coverage = self._coverage
        shown = coverage is not None and self._coverage_shown
        files, directories = (coverage.file_percents(), coverage.directory_percents()) if shown else ({}, {})
        self._tree.set_coverage(files, directories)
        self._overview_pane.show_coverage(coverage)
        self._mark_lines()

    def _mark_lines(self) -> None:
        code = self._code
        if code.document is None:
            return
        shown = self._coverage is not None and self._coverage_shown
        code.set_coverage(self._coverage.lines_of(code.display_path) or {} if shown else None)

    def _coverage_status(self, code: CodeView) -> str:
        percent = self._coverage.file_percent(code.display_path) if self._coverage else None
        if percent is None:
            return ""
        return coverage_status(percent, self._coverage.is_stale(code.display_path, code.document.mtime))

    def _why_no_coverage(self) -> str:
        if self._coverage_loading:
            return "Still reading the coverage reports"
        if self._coverage_files:
            return "The coverage reports that were named hold nothing for this project"
        return "No coverage report found; run the tests with coverage or start spyc with --coverage FILE"

    def action_toggle_coverage(self) -> None:
        if self._needs_working_tree("Coverage"):
            return
        if self._coverage is None:
            self.notify(self._why_no_coverage())
            return
        self._coverage_shown = not self._coverage_shown
        self.store.set("coverage", self._coverage_shown)
        self._apply_coverage()

    def _index_ready(self, generation: int, index: FileIndex, model: TreeModel, overview: Overview,
                     matcher: PathMatcher) -> None:
        if generation != self._index_generation:
            return
        self.overview, self._matcher, self._paths = overview, matcher, index.paths
        self._index_symbols(generation, index.paths)
        if self.source.editable:
            self._coverage_loading = True
            self._load_coverage(generation, index.paths)
        else:
            self._apply_coverage()
        self._tree.load(model)
        self._overview_pane.show(overview)
        if index.truncated:
            self.notify(f"Only the first {len(index.paths):,} files are listed", severity="warning")
        code = self._code
        start = self._start_location
        focus = code.display_path if code.document is not None else (start.path if start else "")
        if focus:
            self._tree.reveal(focus)
        if self._open_after_listing is not None:
            location, self._open_after_listing = self._open_after_listing, None
            self.open_file(location.path, location.line)

    # Git is asked again on a timer, when the window regains focus, after the
    # editor and on request, and not at all once it is clear that this is not a
    # repository. A repository that takes seconds to answer is left alone by
    # the timer, which would otherwise keep it busy for good.
    def _poll_git(self) -> None:
        if not self._git_slow:
            self._refresh_git()

    def _refresh_git(self) -> None:
        if self.git_enabled and self.source.editable:
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
        if not self.source.editable:
            return
        self._git_slow = slow
        if status is None:
            self.git_enabled = self._git_seen
            return
        changed = not self._git_seen or status != self._git_files
        self._git_seen, self._git_files, self._git_summary = True, status, summary
        self._overview_pane.show_git(summary)
        self._show_title()
        if changed:
            self._tree.set_status(status, directories)
            self._refresh_changes()
            self._refresh_blame()

    # The column of marks is reserved the moment a file is shown, and filled
    # in when git has answered.
    def _refresh_changes(self) -> None:
        code = self._code
        if not (self.git_enabled and self._git_seen and self.source.editable) or code.document is None:
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
        if event.state is WorkerState.ERROR and event.worker.group == "symbols":
            self._graph_failed(event.worker.error)
        if event.state is WorkerState.ERROR and event.worker.group == "coverage":
            self._coverage_loading = False
            self.notify(f"Could not read the coverage reports: {printable(str(event.worker.error))}", severity="error",
                        markup=False)

    def open_file(self, path: str, line: int | None = None, column: int = 0) -> None:
        leaving = self._current_place()
        if self._display_file(path, line, column):
            self.history.navigate(leaving, Place(path, line or 1))

    def _display_file(self, path: str, line: int | None, column: int = 0) -> bool:
        try:
            document = self.source.document(path)
        except OSError as error:
            self.notify(f"Cannot open {printable(path)}: {error.strerror or error}", severity="error", markup=False)
            return False
        code = self._code
        code.show(document, path)
        self._overview_pane.display = False
        self._rendered.display = False
        code.display = True
        if line:
            self.call_after_refresh(code.goto, line, column)
        if self.source.editable:
            self.store.add_recent_file(self.project_root, path)
        self._tree.reveal(path)
        code.focus()
        self._mark_lines()
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
        if self.screen_stack:
            self._refresh_status()

    def _refresh_status(self) -> None:
        code = self._code
        document = code.document
        if document is not None:
            language = document.language.name if document.language else None
            extra = " · ".join(part for part in (code.match_status, self._coverage_status(code)) if part)
            self._status.show(code.display_path, language, code.cursor_row, code.cursor_column,
                              len(document.lines), extra)

    def action_find_file(self) -> None:
        if self._matcher is None:
            self.notify("Still reading the project files")
            return
        source = FilePickerSource(self.source, self._matcher, lambda: self.store.recent_files(self.project_root))
        self.push_screen(Picker(source), self._file_chosen)

    def action_search_project(self) -> None:
        if self._paths is None:
            self.notify("Still reading the project files")
            return
        self.push_screen(Picker(SearchSource(self.source, lambda: self._paths)), self._file_chosen)

    def _viewing_for(self, purpose: str) -> CodeView | None:
        code = self._viewing()
        if code is None:
            self.notify("Press r to leave the rendered view first" if self._rendered.display
                        else f"Open a file to {purpose}")
        return code

    def action_show_outline(self) -> None:
        code = self._viewing_for("see its outline")
        if code is None:
            return
        symbols = self._outline_of(code)
        if not symbols:
            self.notify("No outline for this file")
            return
        entries = [Located(code.display_path, symbol) for symbol in symbols]
        source = SymbolSource(self.source, lambda: entries, "Jump to a definition in this file", False)
        self.push_screen(Picker(source), self._file_chosen)

    def action_find_symbol(self) -> None:
        source = SymbolSource(self.source, self._symbols.all, "Find a definition in the project", True,
                              self._symbol_progress, LIST_LIMIT)
        self.push_screen(Picker(source), self._file_chosen)

    def _symbol_progress(self) -> str:
        done, total = self._symbols.done, self._symbols.total
        return f"indexing {done}/{total}" if done < total else ""

    # The name under the cursor is looked up among the definitions of the
    # project, the nearest first. With none but the one under the cursor the
    # places where the name is used are more useful than nothing.
    def action_go_to_definition(self) -> None:
        code = self._viewing_for("look up a definition")
        if code is None:
            return
        word = code.word_at_cursor()
        if word is None:
            self.notify("Put the cursor on a name first")
            return
        here = (code.display_path, code.cursor_row + 1)
        candidates = [item for item in self._definitions_of(word, code) if (item.path, item.symbol.line) != here]
        if len(candidates) == 1 and detect_language(candidates[0].path) == code.document.language:
            self.open_file(candidates[0].path, candidates[0].symbol.line, candidates[0].symbol.column)
        elif candidates:
            source = SymbolSource(self.source, lambda: candidates, f"Definitions of {printable(word)}", True)
            self.push_screen(Picker(source), self._file_chosen)
        else:
            self.notify(f"No definition of {printable(word)} found{self._index_progress_note()}; showing where it is used",
                        markup=False)
            source = SearchSource(self.source, lambda: self._paths or (), whole_word=True)
            self.push_screen(Picker(source, word), self._file_chosen)

    def _index_progress_note(self) -> str:
        return " yet, the index is still being built" if self._symbols.done < self._symbols.total else ""

    # A file that is too big or has too long lines to be colored is not parsed either.
    @staticmethod
    def _outline_of(code: CodeView) -> list[Symbol]:
        document = code.document
        return [] if document.plain else symbols_of(document.text, document.language)

    def _definitions_of(self, word: str, code: CodeView) -> list[Located]:
        current = [Located(code.display_path, symbol) for symbol in self._outline_of(code) if symbol.name == word]
        elsewhere = [item for item in self._symbols.lookup(word) if item.path != code.display_path]
        return sorted(current + elsewhere, key=lambda item: _nearness(item, code.display_path))

    def _file_chosen(self, choice: Choice | None) -> None:
        if choice is not None:
            self.open_file(choice.key, choice.line, choice.column)

    def action_search_in_file(self) -> None:
        if self._viewing_for("search in it") is not None:
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
        if self._viewing_for("go to a line") is not None:
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
            self.push_screen(LogScreen(self.git, focus=self.source.commit), self._location_chosen)

    def action_show_file_log(self) -> None:
        if not self._in_git():
            return
        code = self._code
        if code.document is None:
            self.notify("Open a file to see its history")
            return
        self.push_screen(LogScreen(self.git, code.display_path, self.source.commit), self._location_chosen)

    def action_show_changes(self) -> None:
        if self._in_git() and not self._needs_working_tree("Showing the working-tree changes"):
            self.push_screen(ChangesScreen(lambda: self.git.working_diff(self._untracked_files())), self._location_chosen)

    def action_show_branches(self) -> None:
        if self._in_git():
            self.push_screen(BranchesScreen(self.git), self._branch_chosen)

    # Choosing the working tree while on it keeps the open file and the history.
    # A file chosen in the log or the diff of a branch is opened once the files of
    # the branch are listed, so that the interface never waits for the listing.
    def _branch_chosen(self, pick: BranchPick | None) -> None:
        if pick is None or (pick.branch is None and self.source.editable):
            return
        if pick.branch is None:
            self._leave_branch()
        elif not self._enter_branch(pick.branch):
            return
        self._open_after_listing = pick.location

    # The commit is fixed when the branch is chosen, so a branch that moves, or
    # is deleted, does not change what is on the screen.
    def _enter_branch(self, branch: Branch) -> bool:
        if self.git.fetches_missing_blobs():
            self.notify("This is a partial clone, and this git would fetch the missing files from the remote while "
                        "a branch is read; use git 2.44 or newer, or a full clone", severity="warning")
            return False
        source = GitRefSource(self.git, branch.commit, branch.name)
        self._switch_source(source, SymbolIndex(self.project_root, ref_cache_path(self.project_root), source))
        return True

    def _leave_branch(self) -> None:
        self._switch_source(self._disk, self._disk_symbols)
        self._refresh_git()

    def _switch_source(self, source: FileSource, symbols: SymbolIndex) -> None:
        if isinstance(self.source, GitRefSource):
            self.source.close()
        self.source, self._symbols = source, symbols
        self._about = About(symbols, lambda: self._paths, lambda: self._graph)
        self._graph = self._graph_failure = self._coverage = self._matcher = self._paths = None
        self.history = JumpHistory()
        self._show_no_file()
        if not source.editable:
            self._git_files = {}
            self._tree.set_status({}, {})
        self._overview_pane.show_git(self._git_summary if source.editable else None)
        self._show_title()
        self._reload_index()

    # The open file belonged to the other source, and a document of a branch
    # must never be reloaded from the working tree.
    def _show_no_file(self) -> None:
        code = self._code
        code.document, code.display_path = None, ""
        code.set_changes(None)
        code.set_blame(None)
        code.set_coverage(None)
        self.action_overview()

    def _show_title(self) -> None:
        if self.source.editable:
            summary = self._git_summary
            self.sub_title = printable(f"{self.project_root}  ⎇ {summary.branch}" if summary and summary.branch
                                       else str(self.project_root))
        else:
            self.sub_title = printable(f"{self.project_root}  ⎇ {self.source.ref} @ {self.source.commit[:7]} (read-only)")

    def _needs_working_tree(self, what: str) -> bool:
        if not self.source.editable:
            self.notify(f"{what} needs the working tree; leave the branch view first (B)")
        return not self.source.editable

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
        self._load_blame(code.display_path, self.source.commit)

    @work(thread=True, exclusive=True, group="git-blame", exit_on_error=False)
    def _load_blame(self, path: str, revision: str | None) -> None:
        self.call_from_thread(self._blame_ready, path, self.git.blame(path, revision))

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
        if code is None or self._needs_working_tree("Editing"):
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
        if document is None or not self.source.editable:
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
        self._mark_lines()
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
        self._show_sidebar(not self._tree.display)
        self.store.set("sidebar", self._tree.display)

    def action_widen_sidebar(self) -> None:
        self._resize_sidebar(self._sidebar_width + SIDEBAR_STEP)

    def action_narrow_sidebar(self) -> None:
        self._resize_sidebar(self._sidebar_width - SIDEBAR_STEP)

    def on_splitter_moved(self, message: Splitter.Moved) -> None:
        self._resize_sidebar(message.x)

    def on_resize(self) -> None:
        self._apply_sidebar_width()

    def _show_sidebar(self, shown: bool) -> None:
        self._tree.display = self.screen_stack[0].query_one(Splitter).display = shown

    def _resize_sidebar(self, width: int) -> None:
        self._sidebar_width = self._fit_sidebar_width(width)
        self._apply_sidebar_width()
        self.store.set("sidebar_width", self._sidebar_width)

    # The preferred width is kept as it is when the terminal is too narrow for it, so it comes back when the
    # terminal grows again.
    def _apply_sidebar_width(self) -> None:
        self._tree.styles.width = self._fit_sidebar_width(self._sidebar_width)

    def _fit_sidebar_width(self, width: int) -> int:
        widest = max(MIN_SIDEBAR_WIDTH, self.size.width - MIN_MAIN_WIDTH - 1)
        return min(max(width, MIN_SIDEBAR_WIDTH), widest)

    def action_toggle_ignored(self) -> None:
        if self._needs_working_tree("Showing ignored files"):
            return
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
