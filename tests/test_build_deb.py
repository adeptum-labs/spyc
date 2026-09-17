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


import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "packaging" / "build_deb.py"
spec = importlib.util.spec_from_file_location("build_deb", SCRIPT)
build_deb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_deb)

PROJECT = {
    "name": "spyc",
    "version": "1.2.3",
    "description": "Terminal viewer for browsing code bases",
    "authors": [{"name": "Adam Waldenberg, Adeptum AB", "email": "info@adeptum.se"}],
    "dependencies": ["textual>=8.2", "tree-sitter>=0.25", "pygments>=2.19", "tree-sitter-python", "tree-sitter-c"],
}


def fields(text):
    return dict(line.split(": ", 1) for line in text.splitlines() if line and not line.startswith(" "))


def test_control_names_the_package_version_and_architecture():
    control = fields(build_deb.control_text(PROJECT, "arm64"))
    assert (control["Package"], control["Version"], control["Architecture"]) == ("spyc", "1.2.3-1", "arm64")


def test_control_depends_on_git_and_recommends_ripgrep():
    control = fields(build_deb.control_text(PROJECT, "amd64"))
    assert (control["Depends"], control["Recommends"]) == ("git", "ripgrep")


def test_control_takes_maintainer_and_summary_from_the_project():
    control = fields(build_deb.control_text(PROJECT, "amd64"))
    assert control["Maintainer"] == "Adam Waldenberg, Adeptum AB <info@adeptum.se>"
    assert control["Description"] == "Terminal viewer for browsing code bases"


def test_control_ends_with_a_newline_and_indents_the_long_description():
    text = build_deb.control_text(PROJECT, "amd64")
    lines = text.splitlines()
    assert text.endswith("\n")
    assert all(line.startswith(" ") for line in lines[lines.index(f"Description: {PROJECT['description']}") + 1:])


@pytest.fixture
def tree(tmp_path):
    bundle = tmp_path / "bundle"
    (bundle / "_internal").mkdir(parents=True)
    executable = bundle / "spyc"
    executable.write_text("#!/bin/sh\n")
    executable.chmod(0o755)
    (bundle / "_internal" / "data").write_text("x")
    target = tmp_path / "tree"
    build_deb.assemble(target, bundle, PROJECT, "amd64")
    return target


def test_the_bundle_is_installed_under_usr_lib(tree):
    assert (tree / "usr/lib/spyc/_internal/data").read_text() == "x"


def test_the_executable_keeps_its_executable_bit(tree):
    assert os.access(tree / "usr/lib/spyc/spyc", os.X_OK)


def test_usr_bin_links_to_the_bundle_with_a_relative_path(tree):
    link = tree / "usr/bin/spyc"
    assert link.is_symlink()
    assert os.readlink(link) == "../lib/spyc/spyc"
    assert link.resolve() == (tree / "usr/lib/spyc/spyc").resolve()


def test_copyright_points_at_the_system_gpl_text(tree):
    text = (tree / "usr/share/doc/spyc/copyright").read_text()
    assert "GPL-3+" in text
    assert "/usr/share/common-licenses/GPL-3" in text


def test_the_control_file_is_written_for_the_architecture(tree):
    assert "Architecture: amd64" in (tree / "DEBIAN/control").read_text()


def test_the_host_architecture_comes_from_dpkg():
    calls = []

    def run(command, **options):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="arm64\n")

    assert build_deb.host_architecture(run) == "arm64"
    assert calls == [["dpkg", "--print-architecture"]]


def flags(command, name):
    return [command[index + 1] for index, argument in enumerate(command) if argument == name]


def test_the_pyinstaller_command_bundles_the_queries_and_the_dynamic_libraries(tmp_path):
    command = build_deb.pyinstaller_command(tmp_path, onefile=False, project=PROJECT)
    assert command[:3] == [build_deb.sys.executable, "-m", "PyInstaller"]
    assert f"{build_deb.ROOT / 'src/spyc/syntax/queries'}:spyc/syntax/queries" in flags(command, "--add-data")
    assert {"textual", "tree_sitter"} <= set(flags(command, "--collect-all"))
    assert set(flags(command, "--collect-submodules")) == {"rich", "pygments"}


def test_every_grammar_that_a_language_names_is_collected(tmp_path):
    from spyc.languages import LANGUAGES
    command = build_deb.pyinstaller_command(tmp_path, onefile=False, project=PROJECT)
    wanted = {language.grammar[0] for language in LANGUAGES if language.grammar}
    assert len(wanted) >= 15 and wanted <= set(flags(command, "--collect-all"))


@pytest.mark.parametrize(("onefile", "flag", "other"), [(False, "--onedir", "--onefile"), (True, "--onefile", "--onedir")])
def test_the_layout_follows_the_onefile_switch(tmp_path, onefile, flag, other):
    command = build_deb.pyinstaller_command(tmp_path, onefile, PROJECT)
    assert flag in command
    assert other not in command


def test_the_bundle_carries_the_metadata_of_spyc_and_of_the_tree_sitter_packages(tmp_path):
    command = build_deb.pyinstaller_command(tmp_path, onefile=False, project=PROJECT)
    assert flags(command, "--copy-metadata") == ["spyc", "tree-sitter", "tree-sitter-python", "tree-sitter-c"]


def test_the_real_dependencies_all_have_metadata_to_copy(tmp_path):
    command = build_deb.pyinstaller_command(tmp_path, onefile=False)
    assert len(flags(command, "--copy-metadata")) == 20
