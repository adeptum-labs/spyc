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


def test_it_lists_reads_stamps_and_loads_like_the_functions_it_wraps(tmp_path):
    write_files(tmp_path, {"a.py": "x = 1\n", "sub/b.txt": "hello\n"})
    source = DiskSource(tmp_path)
    assert source.list_files(False, 100).paths == ("a.py", "sub/b.txt")
    assert source.read("a.py", 100) == b"x = 1\n"
    assert source.read("a.py", 3) is None
    assert source.read("missing", 100) is None
    stamp = source.stamp("a.py")
    assert stamp.size == 6 and len(stamp.token) == 2
    assert source.stamp("missing") is None
    assert source.document("sub/b.txt").lines == ("hello",)


def test_it_is_the_working_tree(tmp_path):
    source = DiskSource(tmp_path)
    assert (source.ref, source.commit, source.editable) == (None, None, True)


def test_a_changed_file_gets_another_stamp(tmp_path):
    write_files(tmp_path, {"a.py": "x = 1\n"})
    source = DiskSource(tmp_path)
    before = source.stamp("a.py")
    (tmp_path / "a.py").write_text("x = 22\n")
    assert source.stamp("a.py") != before
