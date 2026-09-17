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
from pathlib import Path

import pytest

from spyc.coverage.resolve import PathResolver

ROOT = Path("/work/project")
PATHS = ("src/a.py", "lib/pkg/b.py", "src/main/java/com/acme/Foo.java", "pkg/a.go", "main.go", "x/util.py", "y/util.py",
         "a/src/main/java/com/acme/Shared.java", "b/src/main/java/com/acme/Shared.java")


@pytest.fixture
def resolver():
    return PathResolver(ROOT, PATHS)


@pytest.mark.parametrize("reported, expected", [
    ("src/a.py", "src/a.py"),
    ("./src/a.py", "src/a.py"),
    ("src\\a.py", "src/a.py"),
    ("/work/project/src/a.py", "src/a.py"),
    ("/home/runner/work/other/checkout/src/a.py", "src/a.py"),
    ("com/acme/Foo.java", "src/main/java/com/acme/Foo.java"),
    ("example.com/acme/proj/pkg/a.go", "pkg/a.go"),
    ("example.com/acme/proj/main.go", "main.go"),
    ("a/b/c.py", None),
    ("src/nothing.py", None),
    ("y/other/util.py", None),
    ("", None)])
def test_a_reported_path_is_matched_to_the_file_it_names(resolver, reported, expected):
    assert resolver.resolve(reported) == expected


def test_a_source_root_of_the_report_completes_a_relative_path(resolver):
    assert resolver.resolve("pkg/b.py", source_roots=("lib",)) == "lib/pkg/b.py"
    assert resolver.resolve("pkg/b.py", source_roots=("/work/project/lib",)) == "lib/pkg/b.py"


def test_a_name_that_fits_two_files_equally_well_is_left_unmatched(resolver):
    assert resolver.resolve("util.py") is None


def test_the_place_of_the_report_breaks_a_tie_and_when_that_does_not_the_name_stays_unmatched(resolver):
    assert resolver.resolve("com/acme/Shared.java", report_directory="b/build/reports") == \
        "b/src/main/java/com/acme/Shared.java"
    assert resolver.resolve("com/acme/Shared.java", report_directory="c/build") is None
    assert resolver.resolve("com/acme/Shared.java") is None


def test_a_path_relative_to_the_place_of_the_report_beats_the_same_path_at_the_root():
    resolver = PathResolver(ROOT, ("src/index.ts", "packages/foo/src/index.ts", "packages/bar/src/index.ts"))
    assert resolver.resolve("src/index.ts", report_directory="packages/foo/coverage") == "packages/foo/src/index.ts"
    assert resolver.resolve("src/index.ts", report_directory="packages/bar") == "packages/bar/src/index.ts"
    assert resolver.resolve("src/index.ts", report_directory="coverage") == "src/index.ts"
    assert resolver.resolve("src/index.ts") == "src/index.ts"


def test_a_name_that_many_files_share_is_resolved_without_a_quadratic_search():
    resolver = PathResolver(ROOT, [f"pkg{index}/index.js" for index in range(3000)])
    started = time.perf_counter()
    for _ in range(20):
        assert resolver.resolve("index.js") is None
    assert time.perf_counter() - started < 1
