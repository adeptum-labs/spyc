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


import json
import os
import shutil
import subprocess
import threading
from collections import deque
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from spyc.core.cancellation import Cancellation

MODEL_VARIABLE = "SPYC_CLAUDE_MODEL"
DEFAULT_MODEL = "sonnet"
STATUS_TIMEOUT = 10
ASK_TIMEOUT = 300
COMPLAINT_LINES = 20
# Only what reads the project: no shell, no editing and no web.
READ_ONLY_TOOLS = "Read,Grep,Glob"
TOOL_VERBS = {"Read": ("Reading", "file_path"), "Grep": ("Searching", "pattern"), "Glob": ("Listing", "pattern")}


@dataclass(frozen=True)
class Text:
    delta: str


@dataclass(frozen=True)
class Tool:
    detail: str


@dataclass(frozen=True)
class Done:
    text: str


@dataclass(frozen=True)
class Failed:
    message: str


Event = Text | Tool | Done | Failed


@dataclass(frozen=True)
class Claude:
    executable: str
    model: str = DEFAULT_MODEL

    def command(self) -> list[str]:
        return [self.executable, "-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
                "--model", self.model, "--effort", "low", "--tools", READ_ONLY_TOOLS, "--permission-mode", "dontAsk",
                "--restricted", "--strict-mcp-config", "--no-session-persistence", "--max-turns", "15"]

    # The prompt goes in on stdin. Claude ends with one Done or Failed, unless the answer was cancelled.
    def ask(self, prompt: str, root: Path, cancellation: Cancellation, timeout: float = ASK_TIMEOUT) -> Iterator[Event]:
        try:
            process = subprocess.Popen(self.command(), cwd=root, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as error:
            yield Failed(f"Could not run claude: {error}")
            return
        complaints: deque[str] = deque(maxlen=COMPLAINT_LINES)
        timed_out = threading.Event()
        timer = threading.Timer(timeout, lambda: (timed_out.set(), process.kill()))
        drain = threading.Thread(target=_collect, args=(process.stderr, complaints), daemon=True)
        cancellation.on_cancel(process.kill)
        timer.start()
        drain.start()
        final: Event | None = None
        try:
            _send(process, prompt)
            for raw in process.stdout:
                event = parse_event(raw.decode("utf-8", errors="replace"), root)
                if isinstance(event, Done | Failed):
                    final = event
                elif event is not None:
                    yield event
            status = process.wait()
            drain.join()
            if cancellation.cancelled:
                return
            if timed_out.is_set():
                yield Failed(f"Claude took longer than {timeout:g} seconds and was stopped")
            elif final is not None:
                yield final
            else:
                yield Failed(complaints[-1] if complaints else f"claude stopped with status {status}")
        finally:
            timer.cancel()
            process.kill()
            process.wait()
            process.stdout.close()


def _send(process: subprocess.Popen, prompt: str) -> None:
    try:
        process.stdin.write(prompt.encode("utf-8"))
        process.stdin.close()
    except OSError:
        pass


def _collect(stream, lines: deque[str]) -> None:
    for raw in stream:
        if line := raw.decode("utf-8", errors="replace").strip():
            lines.append(line)
    stream.close()


def parse_event(line: str, root: Path) -> Event | None:
    try:
        message = json.loads(line)
    except ValueError:
        return None
    if not isinstance(message, dict):
        return None
    match message.get("type"):
        case "stream_event":
            return _text_of(message.get("event"))
        case "assistant":
            return _tool_of(message.get("message"), root)
        case "result":
            return _result_of(message)
    return None


def _text_of(event) -> Text | None:
    delta = event.get("delta") if isinstance(event, dict) else None
    if isinstance(delta, dict) and delta.get("type") == "text_delta" and isinstance(delta.get("text"), str):
        return Text(delta["text"])
    return None


def _tool_of(message, root: Path) -> Tool | None:
    blocks = message.get("content") if isinstance(message, dict) else None
    for block in blocks if isinstance(blocks, list) else ():
        if isinstance(block, dict) and block.get("type") == "tool_use":
            return Tool(_describe(str(block.get("name")), block.get("input"), root))
    return None


def _describe(name: str, arguments, root: Path) -> str:
    verb, field = TOOL_VERBS.get(name, (None, None))
    subject = arguments.get(field) if verb and isinstance(arguments, dict) else None
    if not isinstance(subject, str):
        return name
    prefix = f"{root}/"
    return f"{verb} {subject.removeprefix(prefix) if name == 'Read' else subject}"


def _result_of(message: dict) -> Done | Failed | None:
    text = message.get("result")
    if not isinstance(text, str):
        return None
    return Failed(text) if message.get("is_error") else Done(text)


def find_claude(which=shutil.which, run=subprocess.run, environ: Mapping[str, str] = os.environ) -> Claude | None:
    executable = which("claude")
    if executable is None:
        return None
    try:
        status = run([executable, "auth", "status", "--json"], capture_output=True, timeout=STATUS_TIMEOUT)
        logged_in = status.returncode == 0 and json.loads(status.stdout).get("loggedIn") is True
    except (OSError, subprocess.TimeoutExpired, ValueError, AttributeError):
        return None
    return Claude(executable, environ.get(MODEL_VARIABLE) or DEFAULT_MODEL) if logged_in else None
