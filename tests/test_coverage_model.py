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


from spyc.coverage.model import CoverageLine, counts, merge_lines


def test_a_line_is_covered_by_any_hit_and_the_counts_are_covered_over_total():
    lines = {1: CoverageLine(3), 2: CoverageLine(0), 3: CoverageLine(1, partial=True)}
    assert counts(lines) == (2, 3)
    assert counts({}) == (0, 0)


def test_merging_keeps_the_most_hits_of_each_line_and_the_lines_of_both():
    first = {1: CoverageLine(3), 2: CoverageLine(0)}
    second = {2: CoverageLine(4), 5: CoverageLine(0)}
    assert merge_lines(first, second) == {1: CoverageLine(3), 2: CoverageLine(4), 5: CoverageLine(0)}


def test_a_line_that_one_report_covered_fully_is_not_partial_after_the_merge():
    partial, full, missed = CoverageLine(2, partial=True), CoverageLine(1), CoverageLine(0)
    assert merge_lines({1: partial}, {1: full})[1] == CoverageLine(2)
    assert merge_lines({1: partial}, {1: partial})[1] == CoverageLine(2, partial=True)
    assert merge_lines({1: partial}, {1: missed})[1] == CoverageLine(2, partial=True)
    assert merge_lines({1: missed}, {1: missed})[1] == CoverageLine(0)
