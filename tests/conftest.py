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


import os

import pytest

from repos import PROJECT_FILES, make_repo, write_files


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch, tmp_path_factory):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path_factory.mktemp("state")))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path_factory.mktemp("cache")))
    # The developer's own git configuration must not change what the tests see.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("RIPGREP_CONFIG_PATH", raising=False)


@pytest.fixture
def git_repo(tmp_path):
    return make_repo(tmp_path / "project", PROJECT_FILES)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "demo"
    write_files(root, {"src/app.py": "def main():\n    return 1\n", "README.md": "# Demo\n", "pom.xml": "<project/>"})
    return root
