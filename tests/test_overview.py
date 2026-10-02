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


import spyc.core.overview
from repos import write_files
from spyc.core.file_index import FileIndex, build_index
from spyc.core.overview import build_overview, summary_text
from spyc.core.source import FileStamp


def overview_of(root, files):
    write_files(root, files)
    return build_overview(build_index(root))


def test_languages_are_shares_of_the_bytes_largest_first(tmp_path):
    overview = overview_of(tmp_path, {"a.py": "x" * 300, "b.py": "x" * 100, "Main.java": "x" * 100,
                                      "pom.xml": "x" * 50, "README.md": "x" * 50, "logo.png": "x" * 999})
    assert [(share.name, share.files, share.percent) for share in overview.languages] == [
        ("Python", 2, 66.7), ("Java", 1, 16.7), ("Markdown", 1, 8.3), ("XML", 1, 8.3)]


def test_name_counts_build_systems_and_key_files(tmp_path):
    overview = overview_of(tmp_path, {"pom.xml": "<project/>", "src/Main.java": "class Main {}", "README.md": "hi"})
    assert overview.name == tmp_path.name and overview.file_count == 3
    assert overview.build_systems == ("Maven",)
    assert [key.path for key in overview.key_files] == ["README.md", "pom.xml", "src/Main.java"]


def test_the_readme_preview_is_cut_to_forty_lines(tmp_path):
    overview = overview_of(tmp_path, {"README.md": "\n".join(f"line {number}" for number in range(100))})
    assert overview.readme.splitlines()[0] == "line 0"
    assert overview.readme.splitlines()[-1] == "line 39"


def test_only_a_readme_in_the_root_is_previewed(tmp_path):
    assert overview_of(tmp_path, {"docs/README.md": "hi"}).readme is None


def test_measuring_stops_at_the_stat_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(spyc.core.overview, "STAT_LIMIT", 2)
    overview = overview_of(tmp_path, {f"f{number}.py": "x" for number in range(5)})
    assert overview.sampled and overview.languages[0].files == 2


def test_a_file_that_vanished_since_indexing_is_skipped(tmp_path):
    write_files(tmp_path, {"a.py": "x", "b.py": "x"})
    index = build_index(tmp_path)
    (tmp_path / "a.py").unlink()
    assert build_overview(index).languages[0].files == 1


def test_an_empty_project_has_no_languages(tmp_path):
    overview = build_overview(build_index(tmp_path))
    assert (overview.file_count, overview.languages, overview.readme) == (0, (), None)


def test_summary_shows_the_facts_and_a_bar_per_language(tmp_path):
    text = summary_text(overview_of(tmp_path, {"a.py": "x", "pom.xml": "x"})).plain
    assert tmp_path.name in text and "2 files" in text and "Maven" in text
    assert "Python" in text and "50.0%" in text and "█" * 10 + "░" * 10 in text


def test_summary_says_when_the_file_list_was_capped(tmp_path):
    write_files(tmp_path, {"a.py": "x"})
    overview = build_overview(build_index(tmp_path, limit=0))
    assert "capped" in summary_text(overview).plain


def test_a_project_of_one_file_says_file_not_files(tmp_path):
    def count_of(root, files):
        return summary_text(overview_of(root, files)).plain.splitlines()[2].split(" · ")[0]

    assert count_of(tmp_path / "one", {"a.py": "x"}) == "1 file"
    assert count_of(tmp_path / "two", {"a.py": "x", "b.py": "y"}) == "2 files"


def test_sizes_and_the_readme_come_from_the_source(tmp_path):
    class Source:
        def stamp(self, path):
            return FileStamp(("x",), 40)

        def read(self, path, limit):
            return b"# From the branch\n"

    index = FileIndex(tmp_path / "missing", ("README.md", "a.py"), False)
    overview = build_overview(index, Source())
    assert overview.readme == "# From the branch"
    assert overview.languages[0].size == 40
