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

from spyc.deps.javascript import ScriptModules, package_name

PATHS = ["src/app.ts", "src/util.ts", "src/lib/index.ts", "src/lib/deep.tsx", "src/old.js", "src/data.json",
         "src/comp/A.tsx", "src/comp/A.css", "top.js", "src/index.ts"]
MODULES = ScriptModules(PATHS)


@pytest.mark.parametrize("specifier, expected", [
    ("./util", "src/util.ts"), ("./util.js", "src/util.ts"), ("./lib", "src/lib/index.ts"),
    ("./lib/deep", "src/lib/deep.tsx"), ("./old", "src/old.js"), ("./data.json", "src/data.json"),
    ("./comp/A", "src/comp/A.tsx"), ("../top", "top.js"), (".", "src/index.ts"), ("./", "src/index.ts")])
def test_a_relative_specifier_finds_the_file_by_the_usual_rules(specifier, expected):
    assert MODULES.resolve("src/app.ts", specifier) == (expected, None)


@pytest.mark.parametrize("specifier", ["./missing", "../../x", "./lib/nothing"])
def test_a_relative_specifier_that_reaches_no_file_gives_nothing_and_is_not_external(specifier):
    assert MODULES.resolve("src/app.ts", specifier) == (None, None)


@pytest.mark.parametrize("specifier, expected", [
    ("react", "react"), ("react/jsx-runtime", "react"), ("@scope/pkg/sub", "@scope/pkg"), ("@scope", "@scope"),
    ("node:fs", "node:fs")])
def test_a_bare_specifier_names_a_package_and_a_scope_is_part_of_the_name(specifier, expected):
    assert MODULES.resolve("src/app.ts", specifier) == (None, expected)
    assert package_name(specifier) == expected


def test_an_absolute_path_is_neither_a_file_of_the_project_nor_a_package():
    assert MODULES.resolve("src/app.ts", "/abs/thing") == (None, None)


def test_the_root_directory_has_an_index_file_too():
    assert ScriptModules(["index.ts"]).resolve("main.js", ".") == ("index.ts", None)
