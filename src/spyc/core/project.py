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


import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

BUILD_MARKERS = {
    "pom.xml": "Maven",
    "build.gradle": "Gradle",
    "build.gradle.kts": "Gradle",
    "settings.gradle": "Gradle",
    "settings.gradle.kts": "Gradle",
    "Cargo.toml": "Cargo",
    "go.mod": "Go modules",
    "package.json": "npm",
    "pyproject.toml": "Python (pyproject)",
    "setup.py": "Python (setuptools)",
    "CMakeLists.txt": "CMake",
    "meson.build": "Meson",
    "Makefile": "Make",
    "composer.json": "Composer",
    "Gemfile": "Bundler",
    "build.sbt": "sbt",
}
KEY_FILE_RULES = (
    ("Readme", r"readme(\.\w+)?"),
    ("License", r"(license|licence|copying)(\.\w+)?"),
    ("Build", r"([^/]+/)?(pom\.xml|build\.gradle(\.kts)?|settings\.gradle(\.kts)?|cargo\.toml|go\.mod"
              r"|package\.json|pyproject\.toml|setup\.py|cmakelists\.txt|meson\.build|makefile)"),
    ("Container", r"([^/]+/)?(dockerfile|containerfile|(docker-)?compose\.ya?ml)"),
    ("CI", r"\.gitlab-ci\.yml|jenkinsfile|\.github/workflows/[^/]+\.ya?ml|\.circleci/config\.yml"),
    ("Entry point", r"(?!.*test)(.*/)?(__main__\.py|main\.(go|rs|py|c|cpp|kt)|main\.java"
                    r"|\w+application\.(java|kt)|index\.[jt]sx?)"),
)
KEY_FILE_PATTERNS = tuple((kind, re.compile(pattern, re.IGNORECASE)) for kind, pattern in KEY_FILE_RULES)
MAX_KEY_FILES_PER_KIND = 10


@dataclass(frozen=True)
class KeyFile:
    kind: str
    path: str


def git_toplevel(directory: Path) -> Path | None:
    try:
        result = subprocess.run(["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
                                capture_output=True, text=True)
    except OSError:
        return None
    return Path(result.stdout.strip()) if result.returncode == 0 else None


def find_root(start: Path) -> Path:
    directory = (start if start.is_dir() else start.parent).resolve()
    toplevel = git_toplevel(directory)
    if toplevel is not None:
        return toplevel
    for candidate in (directory, *directory.parents):
        if any((candidate / marker).exists() for marker in BUILD_MARKERS):
            return candidate
    return directory


def detect_build_systems(paths: Iterable[str]) -> list[str]:
    return sorted({BUILD_MARKERS[PurePosixPath(path).name] for path in paths
                   if path.count("/") <= 1 and PurePosixPath(path).name in BUILD_MARKERS})


def key_files(paths: Iterable[str]) -> list[KeyFile]:
    found: dict[str, list[KeyFile]] = {kind: [] for kind, _ in KEY_FILE_PATTERNS}
    for path in sorted(paths):
        kind = next((kind for kind, pattern in KEY_FILE_PATTERNS if pattern.fullmatch(path)), None)
        if kind is not None and len(found[kind]) < MAX_KEY_FILES_PER_KIND:
            found[kind].append(KeyFile(kind, path))
    return [key for keys in found.values() for key in keys]
