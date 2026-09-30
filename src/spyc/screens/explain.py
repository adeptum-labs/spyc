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


import time
from collections.abc import Callable
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static
from textual.worker import Worker, WorkerState

from spyc.assist.cache import AnswerCache, Cached
from spyc.assist.cli import Claude, Done, Failed, Text as Streamed, Tool
from spyc.assist.targets import Facts, Target, content_hash, prompt_of
from spyc.core.cancellation import Cancellation
from spyc.core.printable import printable
from spyc.core.timeago import age
from spyc.widgets.markdown_pane import MarkdownPane

ANSWER_LIMIT = 50_000
REDRAW_INTERVAL = 0.3
WAITING = "Claude is reading the code. Press Escape to stop."


# What Claude says about a package, directory, file or class, as it is written. The answer of an earlier visit is
# shown at once, marked when the code has changed since; r asks again.
class ExplainScreen(Screen[None]):
    DEFAULT_CSS = """
    ExplainScreen #explain-status { height: 1; padding: 0 1; background: $panel; }
    ExplainScreen MarkdownPane { height: 1fr; }
    """
    BINDINGS = [
        Binding("escape,q", "close", "Back"),
        Binding("r", "ask_again", "Ask again"),
    ]

    def __init__(self, claude: Claude, cache: AnswerCache, root: Path, target: Target,
                 facts: Callable[[Target], Facts]) -> None:
        super().__init__()
        self._claude, self._cache, self._root, self._target, self._facts = claude, cache, root, target, facts
        self._generation = 0
        self._cancellation = Cancellation()
        self._started = 0.0
        self._detail = ""
        self._finished_note: str | None = None
        self._live = ""
        self._redraw_timer = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="explain-status")
        yield MarkdownPane()
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = f"About {printable(self._target.label)}"
        self.query_one(MarkdownPane).focus()
        self.set_interval(1, self._tick)
        self._begin(fresh=False)

    def on_unmount(self) -> None:
        self._generation += 1
        self._cancellation.cancel()

    def action_ask_again(self) -> None:
        self._begin(fresh=True)

    def action_close(self) -> None:
        self._cancellation.cancel()
        self.dismiss(None)

    def _begin(self, fresh: bool) -> None:
        self._cancellation.cancel()
        self._generation += 1
        self._cancellation = Cancellation()
        self._started, self._detail, self._finished_note, self._live = time.monotonic(), "", None, ""
        self._show_status()
        self.call_later(self._show_markdown, WAITING)
        self._ask(self._generation, self._cancellation, fresh)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state is WorkerState.ERROR and event.worker.group == "explain":
            self.call_later(self._failed, f"spyc could not prepare the question: {event.worker.error}")

    @work(thread=True, exclusive=True, group="explain", exit_on_error=False)
    def _ask(self, generation: int, cancellation: Cancellation, fresh: bool) -> None:
        target, identity = self._target, self._target.identity
        current = content_hash(target, self._root)
        cached = None if fresh else self._cache.get(identity)
        if cached is not None:
            self._post(generation, self._cached, cached, cached.content_hash != current)
            return
        for event in self._claude.ask(prompt_of(target, self._facts(target)), self._root, cancellation):
            if isinstance(event, Streamed):
                self._post(generation, self._streamed, event.delta)
            elif isinstance(event, Tool):
                self._post(generation, self._reading, event.detail)
            elif isinstance(event, Done):
                self._cache.put(identity, Cached(current, self._claude.model, time.time(), event.text))
                self._post(generation, self._done, event.text)
            elif isinstance(event, Failed):
                self._post(generation, self._failed, event.message)

    def _post(self, generation: int, callback: Callable, *arguments) -> None:
        self.app.call_from_thread(self._if_current, generation, callback, *arguments)

    async def _if_current(self, generation: int, callback: Callable, *arguments) -> None:
        if generation == self._generation:
            await callback(*arguments)

    async def _cached(self, answer: Cached, stale: bool) -> None:
        when = age(time.time() - answer.when)
        self._finished_note = "cached just now" if when == "now" else f"cached {when} ago"
        if stale:
            self._finished_note += " · code changed since, r asks again"
        self._show_status()
        await self._show_markdown(answer.text)

    async def _streamed(self, delta: str) -> None:
        self._live += delta
        if self._redraw_timer is None:
            self._redraw_timer = self.set_timer(REDRAW_INTERVAL, self._redraw)

    async def _redraw(self) -> None:
        self._redraw_timer = None
        await self._show_markdown(self._live)

    # Text written before a tool is used is Claude thinking aloud, and is not part of the answer.
    async def _reading(self, detail: str) -> None:
        self._detail, self._live = detail, ""
        self._show_status()

    async def _done(self, text: str) -> None:
        self._finished_note = f"{self._claude.model} · {time.monotonic() - self._started:.0f} s"
        self._show_status()
        await self._show_markdown(text)

    async def _failed(self, message: str) -> None:
        self._finished_note = "failed · r tries again"
        self._show_status()
        await self._show_markdown(f"Claude could not answer.\n\n> {printable(message)}")

    async def _show_markdown(self, text: str) -> None:
        shown = printable(text, keep_newlines=True)
        await self.query_one(MarkdownPane).show(shown if len(shown) <= ANSWER_LIMIT else shown[:ANSWER_LIMIT] + "\n\n… cut")

    def _tick(self) -> None:
        if self._finished_note is None:
            self._show_status()

    def _show_status(self) -> None:
        if self._finished_note is not None:
            status = self._finished_note
        else:
            parts = [printable(self._claude.model), printable(self._detail), f"{time.monotonic() - self._started:.0f} s"]
            status = " · ".join(part for part in parts if part)
        self.query_one("#explain-status", Static).update(Text(status))
