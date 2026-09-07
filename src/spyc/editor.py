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


import os
import shlex
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path

FALLBACK_EDITORS = ("nvim", "vim", "nano", "vi")
PLUS_LINE = {"vim", "nvim", "vi", "nano", "pico", "emacs", "emacsclient", "gedit", "joe", "ne"}
PATH_COLON_LINE = {"hx", "helix", "micro", "subl", "sublime_text", "zed"}
GOTO_FLAG = {"code", "codium", "code-insiders", "cursor"}
JETBRAINS = {"idea", "pycharm", "goland", "clion", "webstorm", "rustrover"}


def _line_arguments(editor: str, path: str, line: int) -> list[str]:
    name = Path(editor).name
    if name in PLUS_LINE:
        return [f"+{line}", path]
    if name in PATH_COLON_LINE:
        return [f"{path}:{line}"]
    if name in GOTO_FLAG:
        return ["--goto", f"{path}:{line}"]
    if name == "kate":
        return ["-l", str(line), path]
    if name in JETBRAINS:
        return ["--line", str(line), path]
    return [path]


def editor_command(path: Path, line: int, environ: Mapping[str, str] = os.environ,
                   which: Callable[[str], str | None] = shutil.which) -> list[str] | None:
    configured = next((value for name in ("VISUAL", "EDITOR") if (value := environ.get(name, "").strip())), None)
    try:
        words = shlex.split(configured) if configured else [next((name for name in FALLBACK_EDITORS if which(name)), "")]
    except ValueError:
        return None
    if not words or not words[0]:
        return None
    return [*words, *_line_arguments(words[0], str(path), max(line, 1))]
