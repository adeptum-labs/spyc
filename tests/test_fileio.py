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

from spyc.document import load_document
from spyc.fileio import read_limited
from spyc.search import search_text
from spyc.symbol_index import SymbolIndex


def test_a_regular_file_is_read_up_to_the_limit(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"abc")
    assert read_limited(tmp_path / "a.txt", 10) == b"abc"
    assert read_limited(tmp_path / "a.txt", 3) == b"abc"
    assert read_limited(tmp_path / "a.txt", 2) is None


def test_directories_devices_pipes_and_links_to_them_are_not_read(tmp_path):
    os.mkfifo(tmp_path / "pipe")
    (tmp_path / "zero").symlink_to("/dev/zero")
    (tmp_path / "sub").mkdir()
    assert [read_limited(tmp_path / name, 100) for name in ("pipe", "zero", "sub", "missing")] == [None] * 4


def test_the_symbol_index_does_not_hang_on_a_pipe_named_like_source(tmp_path):
    os.mkfifo(tmp_path / "x.py")
    (tmp_path / "y.py").symlink_to("/dev/zero")
    (tmp_path / "ok.py").write_text("def fine(): pass\n")
    index = SymbolIndex(tmp_path)
    index.update(("ok.py", "x.py", "y.py"))
    assert [item.symbol.name for item in index.all()] == ["fine"]


def test_the_python_search_does_not_hang_on_a_pipe(tmp_path):
    os.mkfifo(tmp_path / "x.txt")
    (tmp_path / "ok.txt").write_text("needle\n")
    result = search_text(tmp_path, ("ok.txt", "x.txt"), "needle", ripgrep=False)
    assert [hit.path for hit in result.hits] == ["ok.txt"]


def test_a_pipe_opened_as_a_document_is_a_notice_not_a_hang(tmp_path):
    os.mkfifo(tmp_path / "pipe")
    document = load_document(tmp_path / "pipe")
    assert document.lines == () and document.notice == "Not a regular file"
