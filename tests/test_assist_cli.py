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
import threading
import time
from pathlib import Path

import pytest

from fake_claude import install_claude, needs_sh, result, text_delta, tool_use
from spyc.assist.cli import Claude, Done, Failed, Text, Tool, find_claude, parse_event
from spyc.core.cancellation import Cancellation

ROOT = Path("/work/project")


def test_a_text_delta_is_text():
    assert parse_event(text_delta("Hello"), ROOT) == Text("Hello")


def test_a_tool_use_names_what_is_read_relative_to_the_project():
    assert parse_event(tool_use("Read", file_path="/work/project/src/a.py"), ROOT) == Tool("Reading src/a.py")
    assert parse_event(tool_use("Read", file_path="/elsewhere/b.py"), ROOT) == Tool("Reading /elsewhere/b.py")


def test_a_search_and_a_listing_are_described():
    assert parse_event(tool_use("Grep", pattern="def main"), ROOT) == Tool("Searching def main")
    assert parse_event(tool_use("Glob", pattern="**/*.py"), ROOT) == Tool("Listing **/*.py")


def test_an_unknown_tool_is_named_as_it_is():
    assert parse_event(tool_use("Other", thing=1), ROOT) == Tool("Other")


def test_a_result_is_the_final_answer_or_a_failure():
    assert parse_event(result("All done"), ROOT) == Done("All done")
    assert parse_event(result("Not logged in", error=True), ROOT) == Failed("Not logged in")


@pytest.mark.parametrize("line", ["", "not json", "[1, 2]", "42", '{"type": "system"}', '{"type": "stream_event", "event": 3}',
                                  '{"type": "assistant", "message": {"content": "text"}}', '{"type": "result"}', '{"type": "result", "result": 5}'])
def test_a_line_that_says_nothing_useful_is_skipped(line):
    assert parse_event(line, ROOT) is None


def test_the_command_limits_claude_to_reading_the_project():
    command = Claude("/bin/claude", "sonnet").command()
    assert command[:2] == ["/bin/claude", "-p"]
    for flag, value in [("--model", "sonnet"), ("--effort", "low"), ("--tools", "Read,Grep,Glob"), ("--permission-mode", "dontAsk")]:
        assert command[command.index(flag) + 1] == value
    assert {"--restricted", "--strict-mcp-config", "--no-session-persistence"} <= set(command)


@needs_sh
def test_claude_that_is_logged_in_is_found(tmp_path, monkeypatch):
    install_claude(tmp_path, monkeypatch)
    claude = find_claude()
    assert claude is not None and claude.executable == str(tmp_path / "claude")


@needs_sh
@pytest.mark.parametrize("auth, status", [('{"loggedIn": false}', 0), ('{"loggedIn": false}', 1), ("not json", 0), ("[]", 0), ('{"loggedIn": "yes"}', 0),
                                          ('{"loggedIn": true}', 1), ("", 0)])
def test_claude_that_is_logged_out_or_unreadable_is_not_found(tmp_path, monkeypatch, auth, status):
    install_claude(tmp_path, monkeypatch, auth=auth, auth_status=status)
    assert find_claude() is None


def test_a_missing_claude_is_not_found():
    assert find_claude(which=lambda name: None) is None


def test_claude_that_cannot_be_run_or_hangs_is_not_found():
    def broken(*arguments, **options):
        raise OSError("exec format error")

    def hanging(*arguments, **options):
        raise subprocess.TimeoutExpired("claude", 10)

    assert find_claude(which=lambda name: "claude", run=broken) is None
    assert find_claude(which=lambda name: "claude", run=hanging) is None


@needs_sh
def test_the_model_comes_from_the_environment_or_is_sonnet(tmp_path, monkeypatch):
    install_claude(tmp_path, monkeypatch)
    assert find_claude(environ={}).model == "sonnet"
    assert find_claude(environ={"SPYC_CLAUDE_MODEL": "opus"}).model == "opus"
    assert find_claude(environ={"SPYC_CLAUDE_MODEL": ""}).model == "sonnet"


def ask(claude, prompt="Explain", root=Path("."), cancellation=None, timeout=30):
    return list(claude.ask(prompt, root, cancellation or Cancellation(), timeout))


@needs_sh
def test_an_answer_streams_text_tools_and_the_final_result(tmp_path, monkeypatch):
    fake = install_claude(tmp_path / "bin", monkeypatch, stream=(text_delta("Look"), tool_use("Read", file_path=f"{tmp_path}/a.py"),
                                                                 text_delta("It "), text_delta("is."), result("It is.")))
    events = ask(Claude(str(tmp_path / "bin" / "claude"), "sonnet"), "What is a?", tmp_path)
    assert events == [Text("Look"), Tool("Reading a.py"), Text("It "), Text("is."), Done("It is.")]
    assert fake.prompt == "What is a?" and fake.runs == 1 and "--model sonnet" in fake.arguments[0]


@needs_sh
def test_claude_runs_in_the_project(tmp_path, monkeypatch):
    install_claude(tmp_path / "bin", monkeypatch)
    (tmp_path / "bin" / "claude").write_text("#!/bin/sh\ncat > /dev/null\npwd > where.txt\n")
    ask(Claude(str(tmp_path / "bin" / "claude"), "sonnet"), root=tmp_path)
    assert (tmp_path / "where.txt").read_text().strip() == str(tmp_path.resolve())


@needs_sh
def test_a_failed_result_is_reported_once(tmp_path, monkeypatch):
    install_claude(tmp_path, monkeypatch, stream=(text_delta("x"), result("Credit balance is too low", error=True)), status=1)
    assert ask(Claude(str(tmp_path / "claude"), "sonnet")) == [Text("x"), Failed("Credit balance is too low")]


@needs_sh
def test_an_exit_without_a_result_reports_the_last_line_claude_complained_about(tmp_path, monkeypatch):
    install_claude(tmp_path, monkeypatch, status=1, stderr="warning\nError: unknown option '--tools'\n")
    assert ask(Claude(str(tmp_path / "claude"), "sonnet")) == [Failed("Error: unknown option '--tools'")]


@needs_sh
def test_an_exit_without_a_result_and_without_a_message_reports_the_status(tmp_path, monkeypatch):
    install_claude(tmp_path, monkeypatch, status=3)
    assert ask(Claude(str(tmp_path / "claude"), "sonnet")) == [Failed("claude stopped with status 3")]


@needs_sh
def test_a_claude_that_cannot_be_started_is_reported(tmp_path):
    (tmp_path / "claude").write_text("#!/no/such/interpreter\n")
    (tmp_path / "claude").chmod(0o755)
    [failure] = ask(Claude(str(tmp_path / "claude"), "sonnet"))
    assert isinstance(failure, Failed) and failure.message.startswith("Could not run claude")


@needs_sh
def test_a_lot_of_complaints_do_not_block_claude(tmp_path, monkeypatch):
    install_claude(tmp_path, monkeypatch, stream=(result("Fine"),), stderr="noise\n" * 100_000)
    assert ask(Claude(str(tmp_path / "claude"), "sonnet")) == [Done("Fine")]


@needs_sh
def test_a_slow_claude_is_stopped_at_the_timeout(tmp_path, monkeypatch):
    install_claude(tmp_path, monkeypatch, pause=30)
    started = time.perf_counter()
    assert ask(Claude(str(tmp_path / "claude"), "sonnet"), timeout=0.5) == [Failed("Claude took longer than 0.5 seconds and was stopped")]
    assert time.perf_counter() - started < 10


@needs_sh
def test_cancelling_kills_claude_and_ends_the_answer_silently(tmp_path, monkeypatch):
    install_claude(tmp_path, monkeypatch, stream=(text_delta("x"),), pause=30)
    cancellation = Cancellation()
    threading.Timer(0.5, cancellation.cancel).start()
    started = time.perf_counter()
    events = ask(Claude(str(tmp_path / "claude"), "sonnet"), cancellation=cancellation)
    assert not any(isinstance(event, Done | Failed) for event in events)
    assert time.perf_counter() - started < 10


@needs_sh
def test_closing_the_answer_early_kills_claude(tmp_path, monkeypatch):
    install_claude(tmp_path, monkeypatch, stream=(text_delta("x"),), pause=30)
    answer = Claude(str(tmp_path / "claude"), "sonnet").ask("p", Path("."), Cancellation(), 30)
    assert next(answer) == Text("x")
    started = time.perf_counter()
    answer.close()
    assert time.perf_counter() - started < 10


@needs_sh
def test_claude_is_not_told_it_runs_inside_claude_code(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    install_claude(tmp_path / "bin", monkeypatch)
    (tmp_path / "bin" / "claude").write_text(f'#!/bin/sh\ncat > /dev/null\necho "[$CLAUDECODE]" > "{tmp_path}/env.txt"\n')
    ask(Claude(str(tmp_path / "bin" / "claude"), "sonnet"))
    assert (tmp_path / "env.txt").read_text().strip() == "[]"
