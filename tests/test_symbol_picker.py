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


from repos import write_files
from spyc.core.source import DiskSource
from spyc.symbol_index import Located
from spyc.symbol_picker import SymbolSource
from spyc.symbols import Symbol

ENTRIES = [
    Located("a.py", Symbol("render", "function", 1, 4)),
    Located("a.py", Symbol("Renderer", "class", 5, 6)),
    Located("src/b.py", Symbol("reader", "function", 2, 4)),
    Located("src/c\x1b.py", Symbol("prerender", "function", 9, 4))]


def source(show_path=True, status=lambda: "", entries=ENTRIES, limit=None):
    return SymbolSource(None, lambda: entries, "Find a definition", show_path, status, limit)


def test_an_empty_query_lists_every_definition_in_order():
    items = source().search("")
    assert [(item.key, item.line) for item in items] == [("a.py", 1), ("a.py", 5), ("src/b.py", 2), ("src/c\x1b.py", 9)]


def test_a_query_ranks_names_and_marks_the_matched_characters():
    items = source().search("render")
    assert [item.label.plain.split()[1] for item in items] == ["render", "Renderer", "prerender"]
    marked = [items[0].label.plain[span.start:span.end] for span in items[0].label.spans if str(span.style) == "bold yellow"]
    assert "".join(marked) == "render"


def test_a_label_names_the_kind_the_name_and_where_it_is():
    label = source().search("reader")[0].label.plain
    assert label.startswith("function") and "reader" in label and label.endswith("src/b.py:2")


def test_the_place_can_be_left_out_when_all_definitions_are_in_one_file():
    assert "a.py" not in source(show_path=False).search("render")[0].label.plain


def test_control_characters_in_a_path_never_reach_the_list():
    assert all("\x1b" not in item.label.plain for item in source().search(""))


def test_the_status_is_whatever_the_owner_says():
    assert source(status=lambda: "indexing 3/9").summary() == "indexing 3/9"


def test_the_preview_loads_the_file_and_a_vanished_file_gives_none(tmp_path):
    write_files(tmp_path, {"a.py": "def render(): pass\n"})
    picker = SymbolSource(DiskSource(tmp_path), lambda: ENTRIES, "x", True)
    item = picker.search("render")[0]
    assert picker.preview(item).lines[0] == "def render(): pass"
    (tmp_path / "a.py").unlink()
    assert picker.preview(item) is None


MANY = [Located(f"src/m{index}.py", Symbol(f"name{index}", "function", index + 1, 4)) for index in range(300)]


def test_the_path_can_be_searched_as_well_as_the_name_when_it_is_shown():
    assert [item.key for item in source().search("b.py")] == ["src/b.py"]
    assert source(show_path=False).search("b.py") == []


def test_a_query_of_a_name_and_a_directory_narrows_to_the_definitions_in_it():
    assert [item.line for item in source().search("render src")] == [9]


def test_the_position_of_the_name_travels_with_the_item():
    assert source().search("reader")[0].column == 4


def test_the_list_of_the_whole_project_is_cut_and_says_how_much_was_left_out():
    picker = source(entries=MANY, limit=200)
    assert len(picker.search("")) == 200
    assert picker.summary() == "200 of 300"
    assert picker.search("name29")[0].key == "src/m29.py" and picker.summary() == ""
    assert len(picker.search("name")) == 200 and picker.summary() == "200 of 300"


def test_the_cut_and_the_progress_of_the_index_are_both_said():
    picker = source(entries=MANY, limit=200, status=lambda: "indexing 3/9")
    picker.search("")
    assert picker.summary() == "indexing 3/9  200 of 300"


def test_an_outline_or_a_list_of_candidates_is_never_cut():
    picker = source(show_path=False, entries=MANY)
    assert len(picker.search("")) == 300 and picker.summary() == ""


def test_only_the_list_of_the_whole_project_is_searched_in_the_background():
    assert source(entries=MANY, limit=200).threaded and not source(entries=MANY).threaded
