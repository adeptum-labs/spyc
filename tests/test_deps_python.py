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

from spyc.deps.facts import Import
from spyc.deps.python import PythonModules

PATHS = ["app.py", "src/pkg/__init__.py", "src/pkg/mod.py", "src/pkg/sub/__init__.py", "src/pkg/sub/leaf.py",
         "src/other/util.py", "src/pkg/util.py", "tools/util.py", "tests/test_mod.py", "ns/deep/thing.py"]
MODULES = PythonModules(PATHS)


def resolve(importer, imported):
    return MODULES.resolve(importer, imported)


def test_a_dotted_import_names_the_module_by_the_end_of_its_path_so_a_src_layout_is_found():
    assert resolve("app.py", Import("pkg.mod")) == ({"src/pkg/mod.py"}, None)


def test_the_name_of_something_inside_a_module_leads_to_the_module():
    assert resolve("app.py", Import("pkg.mod.attr")) == ({"src/pkg/mod.py"}, None)


def test_from_import_takes_submodules_where_the_names_are_modules_and_the_module_where_they_are_not():
    assert resolve("app.py", Import("pkg", names=("mod", "missing"))) == ({"src/pkg/mod.py"}, None)
    assert resolve("app.py", Import("pkg.sub", names=("leaf",))) == ({"src/pkg/sub/leaf.py"}, None)
    assert resolve("app.py", Import("pkg.mod", names=("function",))) == ({"src/pkg/mod.py"}, None)
    assert resolve("app.py", Import("pkg.sub", wildcard=True)) == ({"src/pkg/sub/__init__.py"}, None)


def test_the_standard_library_is_not_external_and_other_names_are_counted_by_their_first_segment():
    assert resolve("app.py", Import("os.path")) == (set(), None)
    assert resolve("app.py", Import("requests.adapters")) == (set(), "requests")
    assert resolve("app.py", Import("numpy", names=("array",))) == (set(), "numpy")


def test_a_module_beside_a_script_or_above_it_is_the_nearest_and_a_tie_gives_no_edge():
    assert resolve("tools/x.py", Import("util")) == ({"tools/util.py"}, None)
    assert resolve("src/other/x.py", Import("util")) == ({"src/other/util.py"}, None)
    assert resolve("app.py", Import("util")) == (set(), None)


def test_a_module_beside_a_module_of_a_package_is_not_importable_by_its_bare_name():
    assert "src/pkg/util.py" not in resolve("src/pkg/mod.py", Import("util"))[0]
    assert resolve("src/pkg/mod.py", Import("", level=1, names=("util",))) == ({"src/pkg/util.py"}, None)


def test_relative_imports_start_at_the_package_of_the_importer_and_climb_one_level_per_extra_dot():
    assert resolve("src/pkg/mod.py", Import("", level=1, names=("util", "sub"))) == (
        {"src/pkg/util.py", "src/pkg/sub/__init__.py"}, None)
    assert resolve("src/pkg/sub/leaf.py", Import("mod", level=2, names=("thing",))) == ({"src/pkg/mod.py"}, None)
    assert resolve("src/pkg/sub/leaf.py", Import("", level=2, names=("mod",))) == ({"src/pkg/mod.py"}, None)
    assert resolve("src/pkg/mod.py", Import("sub.leaf", level=1, names=("x",))) == ({"src/pkg/sub/leaf.py"}, None)


def test_a_relative_import_that_climbs_above_the_project_reaches_nothing_and_is_not_external():
    assert resolve("app.py", Import("x", level=3)) == (set(), None)
    assert resolve("src/pkg/mod.py", Import("nothing", level=1)) == (set(), None)


def test_a_namespace_package_without_init_files_is_found():
    assert resolve("app.py", Import("ns.deep", names=("thing",))) == ({"ns/deep/thing.py"}, None)
    assert resolve("app.py", Import("deep.thing")) == ({"ns/deep/thing.py"}, None)


def test_a_name_that_thousands_of_files_share_gives_no_edge_and_is_fast():
    many = PythonModules([f"pkg{index}/utils.py" for index in range(3000)] + ["app.py"])
    started = time.perf_counter()
    assert all(many.resolve("app.py", Import("utils")) == (set(), None) for _ in range(3000))
    assert time.perf_counter() - started < 2


def test_a_project_of_a_hundred_thousand_modules_is_indexed_and_asked_quickly():
    started = time.perf_counter()
    big = PythonModules([f"a{index // 100}/b{index % 100}/m{index}.py" for index in range(100_000)])
    assert big.resolve("a1/b1/m101.py", Import("m5")) == ({"a0/b5/m5.py"}, None)
    assert time.perf_counter() - started < 5


def test_a_relative_import_in_a_file_at_the_root_finds_its_neighbours():
    modules = PythonModules(["app.py", "x.py", "pkg/__init__.py", "__init__.py"])
    assert modules.resolve("app.py", Import("", level=1, names=("x",))) == ({"x.py"}, None)
    assert modules.resolve("app.py", Import("pkg", level=1)) == ({"pkg/__init__.py"}, None)
    assert modules.resolve("app.py", Import("", level=1, wildcard=True)) == ({"__init__.py"}, None)


SHADOWS = PythonModules([
    "click/__init__.py", "click/types.py", "pkg/__init__.py", "pkg/compat/__init__.py", "pkg/compat/typing.py",
    "vendor/lib/__init__.py", "vendor/lib/json.py", "app/main.py", "proj/__init__.py", "proj/celery.py",
    "app1/__init__.py", "app1/tasks.py", "app1/redis.py", "app2/__init__.py", "app2/cache.py"])


def test_a_standard_library_name_is_never_a_project_file_that_merely_ends_like_it():
    assert SHADOWS.resolve("app/main.py", Import("types")) == (set(), None)
    assert SHADOWS.resolve("app/main.py", Import("typing", names=("Any",))) == (set(), None)
    assert SHADOWS.resolve("app/main.py", Import("json")) == (set(), None)


def test_a_third_party_package_is_not_a_project_file_of_a_package_that_is_named_like_it():
    assert SHADOWS.resolve("proj/celery.py", Import("celery", names=("Celery",))) == (set(), "celery")
    assert SHADOWS.resolve("app1/tasks.py", Import("celery", names=("Celery",))) == (set(), "celery")
    assert SHADOWS.resolve("app2/cache.py", Import("redis")) == (set(), "redis")
    assert SHADOWS.resolve("app1/tasks.py", Import("redis")) == (set(), "redis")


def test_the_full_dotted_path_of_a_module_still_names_it_from_anywhere():
    assert SHADOWS.resolve("app/main.py", Import("click.types")) == ({"click/types.py"}, None)
    assert SHADOWS.resolve("app/main.py", Import("pkg.compat.typing")) == ({"pkg/compat/typing.py"}, None)


def test_a_chain_of_a_thousand_nested_directories_is_indexed_and_asked_without_a_quadratic_cost():
    paths = ["/".join([f"d{level}" for level in range(depth)] + [f"m{depth}.py"]) for depth in range(1, 1000)]
    started = time.perf_counter()
    modules = PythonModules(paths)
    assert modules.resolve(paths[-1], Import("unknown")) == (set(), "unknown")
    assert all(modules.resolve(paths[-1], Import(f"unknown{index}")) == (set(), f"unknown{index}") for index in range(100))
    assert time.perf_counter() - started < 3
