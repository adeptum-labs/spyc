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
from pathlib import Path

PROJECT_FILES = {
    "src/app/main.py": "def main():\n    return 0\n",
    "README.md": "# Project\n\nA test project.\n",
    "pyproject.toml": "[project]\nname = 'project'\n",
    ".gitignore": "build/\n",
}


def git(root: Path, *arguments: str) -> str:
    command = ["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.com", *arguments]
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def write_files(root: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def make_repo(root: Path, files: dict[str, str]) -> Path:
    write_files(root, files)
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "Initial commit")
    return root
