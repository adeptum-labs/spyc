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

from repos import write_files
from spyc.file_index import build_index
from spyc.search import SearchResult
from spyc.search_picker import SearchSource


@pytest.fixture
def source(tmp_path):
    write_files(tmp_path, {"a.py": "def foo():\n    return 1\n", "b.txt": "  a foo here\nfoobar\n", "ctl.txt": "foo \x1b[2J\n"})
    paths = build_index(tmp_path).paths
    return SearchSource(tmp_path, lambda: paths)


def test_each_hit_becomes_an_item_with_its_file_and_line(source):
    items = source.search("foo")
    assert [(item.key, item.line) for item in items] == [
        ("a.py", 1), ("b.txt", 1), ("b.txt", 2), ("ctl.txt", 1)]
    assert items[0].label.plain == "def foo():  a.py:1"


def test_the_matched_text_is_marked_and_leading_blanks_are_dropped(source):
    label = source.search("foo")[1].label
    assert label.plain.startswith("a foo here")
    assert [label.plain[span.start:span.end] for span in label.spans if str(span.style) == "bold yellow"] == ["foo"]


def test_control_characters_in_a_hit_never_reach_the_list(source):
    assert all("\x1b" not in item.label.plain for item in source.search("foo"))


def test_the_modes_start_literal_and_can_be_switched(source):
    assert source.mode_text() == "literal"
    source.toggle_regex()
    assert source.mode_text() == "regex"
    source.toggle_word()
    assert source.mode_text() == "regex · whole word"
    source.toggle_regex()
    assert source.mode_text() == "literal · whole word"


def test_a_whole_word_search_leaves_out_longer_words(source):
    source.toggle_word()
    assert ("b.txt", 2) not in [(item.key, item.line) for item in source.search("foo")]


def test_the_summary_counts_hits_and_reports_a_bad_pattern(source):
    assert source.summary() == ""
    source.search("foo")
    assert source.summary() == "4 hits"
    source.search("nothing here")
    assert source.summary() == "no hits"
    source.toggle_regex()
    source.search("foo(")
    assert source.summary().startswith("Bad pattern")


def test_a_cut_list_says_so(source, monkeypatch):
    monkeypatch.setattr("spyc.search_picker.MAX_HITS", 2)
    source.search("foo")
    assert source.summary() == "2+ hits, the list is cut"


def test_the_preview_loads_the_file_and_a_vanished_file_gives_none(source, tmp_path):
    item = source.search("foo")[0]
    assert source.preview(item).lines[0] == "def foo():"
    (tmp_path / "a.py").unlink()
    assert source.preview(item) is None


def test_a_search_can_start_in_whole_word_mode(tmp_path):
    write_files(tmp_path, {"a.txt": "foo\nfoobar\n"})
    paths = build_index(tmp_path).paths
    picked = SearchSource(tmp_path, lambda: paths, whole_word=True)
    assert picked.mode_text() == "literal · whole word"
    assert [item.line for item in picked.search("foo")] == [1]


def test_a_single_hit_is_not_plural(source):
    assert len(source.search("def foo")) == 1
    assert source.summary() == "1 hit"


def test_without_ripgrep_the_pattern_mode_explains_why_it_is_off(source, monkeypatch):
    monkeypatch.setattr("spyc.search.shutil.which", lambda name: None)
    source.toggle_regex()
    assert source.search("foo") == []
    assert source.summary() == "Pattern search needs ripgrep"


def test_cancelling_stops_the_search_that_is_running(source, monkeypatch):
    cancellations = []

    def fake_search(*arguments, cancellation, **options):
        cancellations.append(cancellation)
        return SearchResult()

    monkeypatch.setattr("spyc.search_picker.search_text", fake_search)
    source.search("a")
    source.cancel()
    assert [cancellation.cancelled for cancellation in cancellations] == [True]
