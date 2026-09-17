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


from pathlib import Path

from spyc.coverage.index import Coverage
from spyc.coverage.model import CoverageLine, Report
from spyc.coverage.reports import LoadedReport
from spyc.coverage.text import coverage_status, percent_style, percent_text, summary_text

ROOT = Path("/work/project")


def test_a_percentage_is_cut_down_never_rounded_up_so_that_only_full_coverage_says_100():
    assert [percent_text(value) for value in (0.0, 0.4, 50.0, 99.6, 100.0)] == ["0%", "0%", "50%", "99%", "100%"]


def test_the_status_names_the_share_and_says_when_the_report_is_older_than_the_file():
    assert coverage_status(83.4, stale=False) == "coverage 83%"
    assert coverage_status(83.4, stale=True) == "coverage 83% (stale)"


def test_the_color_of_a_share_goes_from_red_to_green():
    assert [percent_style(value) for value in (0.0, 49.9, 50.0, 79.9, 80.0, 100.0)] == [
        "red", "red", "yellow", "yellow", "green", "green"]


def test_the_summary_gives_the_share_the_lines_the_formats_and_the_files_that_were_not_found():
    coverage = Coverage.build(ROOT, ("a.py", "b.py"), [
        LoadedReport(ROOT / "lcov.info", 1.0, Report("LCOV", {"a.py": {1: CoverageLine(1), 2: CoverageLine(0)},
                                                                "gone.py": {1: CoverageLine(1)}}))])
    assert summary_text(coverage).plain == "Coverage 50% · 1 of 2 lines · LCOV\n1 file of the reports is not in the project\n"


def test_a_report_without_lines_has_nothing_to_summarise():
    coverage = Coverage.build(ROOT, ("a.py",), [LoadedReport(ROOT / "x.info", 1.0, Report("LCOV", {"a.py": {}}))])
    assert summary_text(coverage).plain == ""
