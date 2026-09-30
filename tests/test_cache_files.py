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


from spyc.core.cache_files import cache_path, write_atomically


def test_a_cache_file_lives_under_xdg_cache_home_per_project_and_name(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache-home"))
    symbols, answers, other = cache_path(tmp_path, "symbols"), cache_path(tmp_path, "claude"), cache_path(tmp_path / "x", "symbols")
    assert symbols.parent == tmp_path / "cache-home" / "spyc"
    assert symbols.name.startswith("symbols-") and answers.name.startswith("claude-")
    assert symbols != answers and symbols != other


def test_writing_replaces_the_file_and_leaves_no_temporary_file(tmp_path):
    target = tmp_path / "cache.json"
    write_atomically(target, "first")
    write_atomically(target, "second")
    assert target.read_text() == "second"
    assert [path.name for path in tmp_path.iterdir()] == ["cache.json"]
