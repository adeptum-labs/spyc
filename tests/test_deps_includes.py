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

import pytest

from spyc.deps.includes import IncludeModules

PATHS = ["src/a.c", "src/a.h", "include/lib/z.h", "include/util.h", "lib/x/util.h", "other/util.h", "app/main.c", "app/local.h",
         "app/sub/deep.h"]
MODULES = IncludeModules(PATHS)


@pytest.mark.parametrize("importer, include, expected", [
    ("app/main.c", '"local.h"', ("app/local.h", None)),
    ("app/main.c", '"sub/deep.h"', ("app/sub/deep.h", None)),
    ("src/a.c", '"a.h"', ("src/a.h", None)),
    ("app/main.c", '"lib/z.h"', ("include/lib/z.h", None)),
    ("app/main.c", "<lib/z.h>", ("include/lib/z.h", None)),
    ("app/main.c", '"util.h"', ("include/util.h", None)),
    ("lib/x/y.c", '"util.h"', ("lib/x/util.h", None)),
    ("app/main.c", "<stdio.h>", (None, None)),
    ("app/main.c", "<boost/asio.hpp>", (None, "boost")),
    ("app/main.c", '"missing.h"', (None, None)),
    ("app/main.c", '"../src/a.h"', ("src/a.h", None)),
    ("app/main.c", '"../../outside.h"', (None, None)),
    ("app/main.c", '"/usr/include/x.h"', (None, None)),
    ("app/main.c", '""', (None, None)),
    ("app/main.c", "<>", (None, None)),
])
def test_an_include_is_found_beside_the_file_in_an_include_directory_or_by_the_end_of_its_path(importer, include, expected):
    assert MODULES.resolve(importer, include) == expected


def test_a_header_name_that_thousands_of_files_share_gives_no_edge_and_is_fast():
    many = IncludeModules([f"d{index}/util.h" for index in range(3000)] + ["main.c"])
    started = time.perf_counter()
    assert all(many.resolve("main.c", '"util.h"') == (None, None) for _ in range(3000))
    assert all(many.resolve("main.c", '"d5/util.h"') == ("d5/util.h", None) for _ in range(3000))
    assert time.perf_counter() - started < 2


def test_the_nearest_of_a_few_headers_with_the_same_name_wins_and_a_tie_gives_nothing():
    modules = IncludeModules(["a/x/util.h", "b/x/util.h", "a/main.c", "c/main.c"])
    assert modules.resolve("a/main.c", '"x/util.h"') == ("a/x/util.h", None)
    assert modules.resolve("c/main.c", '"x/util.h"') == (None, None)


def test_a_thousand_nested_directories_are_no_trouble():
    deep = "/".join(f"d{index}" for index in range(1000))
    modules = IncludeModules([f"{deep}/main.c", "include/x.h"])
    assert modules.resolve(f"{deep}/main.c", '"x.h"') == ("include/x.h", None)


@pytest.mark.parametrize("include", ["<sys/types.h>", "<netinet/in.h>", "<arpa/inet.h>", "<linux/limits.h>", "<bits/stdc++.h>"])
def test_the_directories_of_the_operating_system_headers_are_not_libraries(include):
    assert MODULES.resolve("app/main.c", include) == (None, None)


def test_a_project_header_in_a_directory_named_like_a_system_one_is_still_found():
    assert IncludeModules(["compat/sys/types.h", "a.c"]).resolve("a.c", "<sys/types.h>") == ("compat/sys/types.h", None)
