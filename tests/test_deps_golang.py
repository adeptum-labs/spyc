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

from spyc.deps.facts import FileFacts, Import
from spyc.deps.golang import GoModules


def go(defines=(), language="go", imports=()):
    return FileFacts(language=language, imports=tuple(imports), defines=frozenset(defines))


FILES = {
    "go.mod": go(language="gomod", imports=[Import("example.com/proj")]),
    "cmd/app/main.go": go(["main"]), "pkg/api/handler.go": go(["Handle", "Router"]), "pkg/api/util.go": go(["helper", "Do"]),
    "pkg/api/handler_test.go": go(["TestHandle"]), "pkg/store/store.go": go(["Open"]), "root.go": go(["Root"]),
    "sub/go.mod": go(language="gomod", imports=[Import("example.com/proj/sub")]), "sub/x/x.go": go(["X"]),
}
MODULES = GoModules(FILES)


def resolve(imported):
    return MODULES.resolve("cmd/app/main.go", imported)


def test_an_import_of_a_package_of_the_project_gives_its_directory_and_the_files_that_define_the_names_used():
    assert resolve(Import("example.com/proj/pkg/api", names=("Handle", "Missing"))) == ("pkg/api", {"pkg/api/handler.go"}, None)
    assert resolve(Import("example.com/proj/pkg/api", names=("Do", "Handle"))) == (
        "pkg/api", {"pkg/api/handler.go", "pkg/api/util.go"}, None)


def test_a_package_imported_without_a_used_name_is_reached_as_a_directory_only_and_test_files_are_never_targets():
    assert resolve(Import("example.com/proj/pkg/api")) == ("pkg/api", set(), None)
    assert resolve(Import("example.com/proj/pkg/api", names=("TestHandle",))) == ("pkg/api", set(), None)
    assert resolve(Import("example.com/proj/pkg/api", wildcard=True)) == ("pkg/api", set(), None)


def test_the_root_package_and_a_nested_module_are_found_and_the_longest_module_wins():
    assert resolve(Import("example.com/proj")) == ("", set(), None)
    assert resolve(Import("example.com/proj/sub/x", names=("X",))) == ("sub/x", {"sub/x/x.go"}, None)


def test_a_package_of_the_project_that_does_not_exist_is_neither_reached_nor_external():
    assert resolve(Import("example.com/proj/pkg/nothing")) == (None, set(), None)


def test_the_standard_library_is_nothing_and_a_package_of_another_module_is_counted_by_its_repository():
    assert resolve(Import("fmt")) == (None, set(), None)
    assert resolve(Import("net/http")) == (None, set(), None)
    assert resolve(Import("github.com/spf13/cobra/doc")) == (None, set(), "github.com/spf13/cobra")


def test_with_a_module_file_a_package_of_another_module_is_never_taken_for_a_directory_that_ends_alike():
    assert resolve(Import("github.com/other/pkg/api", names=("Do",))) == (None, set(), "github.com/other/pkg")


def test_without_a_module_file_the_end_of_an_import_path_names_a_directory_of_two_segments_or_more():
    modules = GoModules({path: facts for path, facts in FILES.items() if facts.language != "gomod"})
    assert modules.resolve("cmd/app/main.go", Import("example.com/proj/pkg/api", names=("Do",))) == (
        "pkg/api", {"pkg/api/util.go"}, None)
    assert modules.resolve("cmd/app/main.go", Import("github.com/spf13/cobra")) == (None, set(), "github.com/spf13/cobra")


def test_a_name_shared_by_thousands_of_directories_gives_the_nearest_or_nothing_and_is_fast():
    many = GoModules({f"a{index}/shared/util/u.go": go(["U"]) for index in range(3000)})
    assert many.resolve("main.go", Import("x.com/y/shared/util", names=("U",))) == (None, set(), None)
    few = GoModules({"a/shared/util/u.go": go(["U"]), "b/shared/util/u.go": go(["U"])})
    assert few.resolve("a/main.go", Import("x.com/y/shared/util", names=("U",))) == (
        "a/shared/util", {"a/shared/util/u.go"}, None)
    assert few.resolve("c/main.go", Import("x.com/y/shared/util", names=("U",))) == (None, set(), None)


def test_an_import_path_of_thousands_of_segments_is_resolved_fast_with_and_without_a_module_file():
    started = time.perf_counter()
    long_path = "x.com/" + "/".join(["a"] * 20000)
    modules = GoModules({path: facts for path, facts in FILES.items() if facts.language != "gomod"})
    assert modules.resolve("cmd/app/main.go", Import(long_path)) == (None, set(), "x.com/a/a")
    assert MODULES.resolve("cmd/app/main.go", Import(long_path)) == (None, set(), "x.com/a/a")
    assert time.perf_counter() - started < 0.5
