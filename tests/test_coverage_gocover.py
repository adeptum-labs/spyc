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


import time

from spyc.coverage.gocover import parse_gocover
from spyc.coverage.model import CoverageLine

SAMPLE = """mode: count
example.com/p/a.go:3.10,5.2 1 4
example.com/p/a.go:5.10,6.2 1 0
example.com/p/b.go:1.1,1.20 1 0
example.com/p/b.go:1.1,1.20 1 2
"""


def test_a_block_covers_the_lines_it_spans_and_a_line_of_covered_and_missed_blocks_is_partial():
    report = parse_gocover(SAMPLE)
    assert report.format == "Go"
    assert report.files == {
        "example.com/p/a.go": {3: CoverageLine(4), 4: CoverageLine(4), 5: CoverageLine(4, partial=True),
                               6: CoverageLine(0)},
        "example.com/p/b.go": {1: CoverageLine(2)}}


def test_lines_that_are_not_blocks_are_ignored_and_the_mode_line_is_optional():
    text = "garbage\nc.go:2.1,x.1 1 1\nc.go:2.1,2.9 1 1\r\n\nc.go:9.1,8.1 1 1\n"
    assert parse_gocover(text).files == {"c.go": {2: CoverageLine(1)}}


def test_a_block_that_claims_a_huge_number_of_lines_is_refused_instead_of_expanded():
    started = time.perf_counter()
    report = parse_gocover("mode: set\na.go:1.1,100000000.1 1 1\nb.go:1.1,2.1 1 1\n")
    assert report.files == {"b.go": {1: CoverageLine(1), 2: CoverageLine(1)}}
    assert time.perf_counter() - started < 2


def test_a_report_stops_expanding_lines_once_its_budget_is_spent(monkeypatch):
    monkeypatch.setattr("spyc.coverage.gocover.MAX_EXPANDED_LINES", 10)
    text = "".join(f"f{index}.go:1.1,6.1 1 1\n" for index in range(5))
    assert sum(len(lines) for lines in parse_gocover(text).files.values()) <= 12
