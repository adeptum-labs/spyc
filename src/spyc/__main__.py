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


import argparse
import importlib.metadata
import sys
from pathlib import Path

from spyc.app import SpycApp
from spyc.location import Location, parse_location
from spyc.project import find_root
from spyc.state import configure_logging

DESCRIPTION = "Terminal viewer for browsing code bases: syntax colors, git history and coverage."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spyc", description=DESCRIPTION)
    parser.add_argument("path", nargs="?", default=".", metavar="PATH[:LINE]",
                        help="file or directory to open, the current directory by default")
    parser.add_argument("--coverage", action="append", default=[], metavar="FILE",
                        help="coverage report to show (LCOV, Cobertura, JaCoCo or Go), may be given more than once; "
                             "the reports of the project are looked for when there is none")
    parser.add_argument("--version", action="version", version=f"spyc {importlib.metadata.version('spyc')}")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    location = parse_location(arguments.path)
    target = Path(location.path).expanduser().resolve()
    if not target.exists():
        print(f"spyc: {arguments.path}: no such file or directory", file=sys.stderr)
        return 2
    coverage_files = [Path(name).expanduser().resolve() for name in arguments.coverage]
    missing = next((name for name, path in zip(arguments.coverage, coverage_files) if not path.is_file()), None)
    if missing is not None:
        print(f"spyc: --coverage {missing}: no such file", file=sys.stderr)
        return 2
    root = find_root(target)
    try:
        relative = target.relative_to(root).as_posix()
    except ValueError:
        root = target if target.is_dir() else target.parent
        relative = target.relative_to(root).as_posix()
    configure_logging()
    SpycApp(root, None if relative == "." else Location(relative, location.line), coverage_files=coverage_files).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
