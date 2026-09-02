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


from spyc.file_picker import FilePickerSource
from spyc.fuzzy import PathMatcher

PATHS = ["src/app.py", "README.md", "tests/test_app.py"]


def make_source(tmp_path, recent=()):
    for path in PATHS:
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text("x = 1\n")
    return FilePickerSource(tmp_path, PathMatcher(PATHS), lambda: recent)


def test_items_carry_the_path_and_a_line_suffix(tmp_path):
    item = make_source(tmp_path).search("app.py:40")[0]
    assert (item.key, item.line) == ("src/app.py", 40)


def test_without_a_suffix_there_is_no_line(tmp_path):
    assert make_source(tmp_path).search("app")[0].line is None


def test_the_label_dims_the_directory_and_marks_the_matched_characters(tmp_path):
    label = make_source(tmp_path).search("app")[0].label
    assert label.plain == "src/app.py"
    assert [(span.start, span.end, str(span.style)) for span in label.spans] == [
        (0, 4, "dim"), (4, 5, "bold yellow"), (5, 6, "bold yellow"), (6, 7, "bold yellow")]


def test_an_empty_query_starts_with_the_recent_files(tmp_path):
    assert make_source(tmp_path, recent=["tests/test_app.py"]).search("")[0].key == "tests/test_app.py"


def test_preview_loads_the_file(tmp_path):
    source = make_source(tmp_path)
    assert source.preview(source.search("readme")[0]).lines == ("x = 1",)


def test_preview_of_a_file_that_vanished_is_none(tmp_path):
    source = make_source(tmp_path)
    item = source.search("readme")[0]
    (tmp_path / "README.md").unlink()
    assert source.preview(item) is None
