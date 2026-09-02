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

import spyc.document
from spyc.document import load_document


def write(tmp_path, name, data: bytes):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_lines_without_the_trailing_empty_line(tmp_path):
    assert load_document(write(tmp_path, "a.py", b"a\nb\n")).lines == ("a", "b")


def test_crlf_line_endings_are_stripped(tmp_path):
    assert load_document(write(tmp_path, "a.txt", b"a\r\nb\r\n")).lines == ("a", "b")


def test_invalid_utf8_is_replaced_not_fatal(tmp_path):
    assert load_document(write(tmp_path, "a.c", b"caf\xe9\n")).lines == ("caf�",)


def test_a_byte_order_mark_is_not_shown(tmp_path):
    assert load_document(write(tmp_path, "a.py", b"\xef\xbb\xbfx = 1\n")).lines == ("x = 1",)


def test_empty_file_has_one_empty_line(tmp_path):
    assert load_document(write(tmp_path, "a.py", b"")).lines == ("",)


def test_binary_file_has_a_notice_and_no_lines(tmp_path):
    document = load_document(write(tmp_path, "a.png", b"\x89PNG\x00\x01"))
    assert document.lines == ()
    assert document.notice.startswith("Binary file")


def test_huge_file_is_not_read(tmp_path, monkeypatch):
    monkeypatch.setattr(spyc.document, "FILE_LIMIT", 4)
    document = load_document(write(tmp_path, "a.log", b"0123456789"))
    assert document.lines == ()
    assert "too large" in document.notice


def test_minified_line_turns_off_highlighting(tmp_path):
    document = load_document(write(tmp_path, "bundle.js", b"x" * 20_000))
    assert document.plain and document.lines == ("x" * 20_000,)


def test_large_file_turns_off_highlighting(tmp_path, monkeypatch):
    monkeypatch.setattr(spyc.document, "HIGHLIGHT_LIMIT", 4)
    assert load_document(write(tmp_path, "a.py", b"x = 1\n")).plain


def test_language_comes_from_the_name_or_the_shebang(tmp_path):
    assert load_document(write(tmp_path, "a.rs", b"fn main() {}\n")).language.id == "rust"
    assert load_document(write(tmp_path, "tool", b"#!/usr/bin/env python3\n")).language.id == "python"


def test_directories_raise(tmp_path):
    with pytest.raises(OSError):
        load_document(tmp_path)
