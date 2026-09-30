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
import stat
from dataclasses import dataclass
from pathlib import Path

import pytest

needs_sh = pytest.mark.skipif(shutil.which("sh") is None, reason="a shell script stands in for claude")


def text_delta(text: str) -> str:
    return json.dumps({"type": "stream_event", "event": {"type": "content_block_delta", "index": 0,
                                                         "delta": {"type": "text_delta", "text": text}}})


def tool_use(name: str, **arguments) -> str:
    return json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": arguments}]}})


def result(text: str, *, error: bool = False) -> str:
    return json.dumps({"type": "result", "subtype": "error_during_execution" if error else "success", "is_error": error, "result": text})


@dataclass(frozen=True)
class FakeClaude:
    directory: Path

    @property
    def runs(self) -> int:
        log = self.directory / "runs.log"
        return len(log.read_text().splitlines()) if log.exists() else 0

    @property
    def arguments(self) -> list[str]:
        return (self.directory / "runs.log").read_text().splitlines()

    @property
    def prompt(self) -> str:
        return (self.directory / "prompt.txt").read_text()


# A shell script named claude at the front of the PATH. `claude auth status` prints `auth`; any other call logs its
# arguments and prompt, prints the `stream` lines, waits `pause` seconds and exits with `status`.
def install_claude(directory: Path, monkeypatch, *, auth: str = '{"loggedIn": true}', auth_status: int = 0,
                   stream: tuple[str, ...] = (), status: int = 0, pause: float = 0, stderr: str = "") -> FakeClaude:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "auth.json").write_text(auth)
    (directory / "stream.jsonl").write_text("".join(f"{line}\n" for line in stream))
    (directory / "stderr.txt").write_text(stderr)
    script = directory / "claude"
    script.write_text(f"""#!/bin/sh
if [ "$1" = auth ]; then cat '{directory}/auth.json'; exit {auth_status}; fi
echo "$*" >> '{directory}/runs.log'
cat > '{directory}/prompt.txt'
cat '{directory}/stream.jsonl'
cat '{directory}/stderr.txt' >&2
{f"exec sleep {pause}" if pause else f"exit {status}"}
""")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{directory}:{os.environ['PATH']}")
    return FakeClaude(directory)
