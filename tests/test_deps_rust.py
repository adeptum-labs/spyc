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


import pytest

from spyc.deps.facts import Import
from spyc.deps.rust import RustCrates

CRATES = RustCrates(["src/lib.rs", "src/a/mod.rs", "src/a/b.rs", "src/c.rs", "crates/foo/src/lib.rs", "crates/foo/src/util.rs",
                     "crates/foo-bar/src/main.rs", "tests/it.rs", "build.rs"])


@pytest.mark.parametrize("importer, path, expected", [
    ("src/lib.rs", "crate::a::b::Item", ("src/a/b.rs", None)),
    ("src/a/b.rs", "super::c", ("src/a/mod.rs", None)),
    ("src/a/b.rs", "super::super::c", ("src/c.rs", None)),
    ("src/a/mod.rs", "self::b", ("src/a/b.rs", None)),
    ("src/lib.rs", "self::a", ("src/a/mod.rs", None)),
    ("src/lib.rs", "a::b", ("src/a/b.rs", None)),
    ("src/lib.rs", "crate::missing::Item", ("src/lib.rs", None)),
    ("src/a/b.rs", "std::io", (None, None)),
    ("src/a/b.rs", "core::fmt", (None, None)),
    ("tests/it.rs", "foo::util::thing", ("crates/foo/src/util.rs", None)),
    ("src/lib.rs", "foo_bar::x", ("crates/foo-bar/src/main.rs", None)),
    ("src/lib.rs", "serde::Serialize", (None, "serde")),
    ("src/lib.rs", "Direction::North", (None, None)),
    ("tests/it.rs", "crate::x", (None, None)),
    ("build.rs", "self::x", (None, None)),
    ("src/lib.rs", "super::x", (None, None)),
])
def test_a_path_names_the_deepest_module_file_on_it_and_a_crate_outside_the_project_is_external(importer, path, expected):
    assert CRATES.resolve(importer, Import(path)) == expected


def test_a_mod_declaration_finds_the_file_beside_it_in_both_layouts():
    assert CRATES.resolve("src/lib.rs", Import("self::c")) == ("src/c.rs", None)
    assert CRATES.resolve("src/lib.rs", Import("self::a")) == ("src/a/mod.rs", None)
    assert CRATES.resolve("src/a/mod.rs", Import("self::b")) == ("src/a/b.rs", None)


def test_a_thousand_super_segments_and_a_thousand_nested_directories_are_no_trouble():
    assert CRATES.resolve("src/a/b.rs", Import("::".join(["super"] * 1000 + ["x"]))) == (None, None)
    deep = "/".join(f"d{index}" for index in range(1000))
    crates = RustCrates(["src/lib.rs", f"src/{deep}/x.rs"])
    assert crates.resolve(f"src/{deep}/x.rs", Import("crate::nothing")) == ("src/lib.rs", None)
