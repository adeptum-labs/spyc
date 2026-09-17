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


from spyc.coverage.text import coverage_status, percent_text


def test_a_percentage_is_cut_down_never_rounded_up_so_that_only_full_coverage_says_100():
    assert [percent_text(value) for value in (0.0, 0.4, 50.0, 99.6, 100.0)] == ["0%", "0%", "50%", "99%", "100%"]


def test_the_status_names_the_share_and_says_when_the_report_is_older_than_the_file():
    assert coverage_status(83.4, stale=False) == "coverage 83%"
    assert coverage_status(83.4, stale=True) == "coverage 83% (stale)"
