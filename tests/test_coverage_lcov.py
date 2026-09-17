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


from spyc.coverage.lcov import parse_lcov
from spyc.coverage.model import CoverageLine

SAMPLE = """TN:unit
SF:src/a.js
FN:1,f
FNDA:1,f
DA:1,3
DA:2,0
DA:3,2,abc123
BRDA:3,0,0,1
BRDA:3,0,1,-
LF:3
LH:2
end_of_record
SF:src/a.js
DA:2,4
end_of_record
SF:src/b.js
DA:1,0
BRDA:1,0,0,0
end_of_record
"""


def test_lines_hits_and_partial_branches_are_read_and_records_of_a_file_are_merged():
    report = parse_lcov(SAMPLE)
    assert report.format == "LCOV"
    assert report.files == {
        "src/a.js": {1: CoverageLine(3), 2: CoverageLine(4), 3: CoverageLine(2, partial=True)},
        "src/b.js": {1: CoverageLine(0)}}


def test_malformed_lines_and_windows_line_endings_are_survived():
    text = "SF:c.js\r\nDA:x,y\r\nDA:5\r\nDA:-1,2\r\nnonsense\r\nDA:7,1\r\nend_of_record\r\nDA:9,9\r\n"
    assert parse_lcov(text).files == {"c.js": {7: CoverageLine(1)}}


def test_a_line_with_all_branches_taken_is_not_partial():
    text = "SF:d.js\nDA:1,1\nBRDA:1,0,0,2\nBRDA:1,0,1,1\nend_of_record\n"
    assert parse_lcov(text).files["d.js"][1] == CoverageLine(1)


def test_text_that_is_not_lcov_gives_an_empty_report():
    assert parse_lcov("<xml/>").files == {}
