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
from spyc.coverage.reports import LoadedReport, load_reports
from repos import write_files

ROOT = Path("/work/project")
PATHS = ("src/a.py", "src/b.py", "src/sub/c.py", "lib/d.py", "README.md")


def loaded(files, mtime=100.0, name="lcov.info", format="LCOV", roots=()):
    return LoadedReport(Path("/work/project/coverage") / name, mtime, Report(format, files, roots))


def build(*reports):
    return Coverage.build(ROOT, PATHS, list(reports))


A_LINES = {1: CoverageLine(2), 2: CoverageLine(0), 3: CoverageLine(1, partial=True), 4: CoverageLine(0)}


def test_the_lines_of_a_file_are_found_by_the_path_the_report_used():
    coverage = build(loaded({"/work/project/src/a.py": A_LINES, "elsewhere/x.py": {1: CoverageLine(1)}}))
    assert coverage.lines_of("src/a.py") == A_LINES
    assert coverage.lines_of("src/b.py") is None
    assert coverage.unmatched == 1


def test_reports_of_the_same_file_are_merged_by_the_most_hits():
    first = loaded({"src/a.py": {1: CoverageLine(2), 2: CoverageLine(0)}}, name="unit.info")
    second = loaded({"src/a.py": {2: CoverageLine(5), 9: CoverageLine(0)}}, name="it.info", format="Cobertura")
    coverage = build(first, second)
    assert coverage.lines_of("src/a.py") == {1: CoverageLine(2), 2: CoverageLine(5), 9: CoverageLine(0)}
    assert coverage.formats == ("LCOV", "Cobertura")


def test_percentages_are_covered_lines_over_lines_for_files_directories_and_the_project():
    coverage = build(loaded({"src/a.py": A_LINES, "src/b.py": {1: CoverageLine(1)}, "src/sub/c.py": {1: CoverageLine(0)},
                             "lib/d.py": {}}))
    assert coverage.file_percent("src/a.py") == 50.0
    assert coverage.file_percent("lib/d.py") is None and coverage.file_percent("README.md") is None
    assert coverage.directory_percent("src") == 100 * 3 / 6
    assert coverage.directory_percent("src/sub") == 0.0
    assert coverage.directory_percent("lib") is None
    assert coverage.directory_percent("") == 100 * 3 / 6
    assert coverage.total == (3, 6)


def test_a_file_changed_after_its_report_is_stale():
    coverage = build(loaded({"src/a.py": A_LINES}, mtime=1000.0))
    assert coverage.is_stale("src/a.py", 1000.5) is False
    assert coverage.is_stale("src/a.py", 1002.0) is True
    assert coverage.is_stale("src/b.py", 2000.0) is False


def test_a_merged_file_is_as_stale_as_the_oldest_report_that_covers_it():
    coverage = build(loaded({"src/a.py": A_LINES}, mtime=1000.0), loaded({"src/a.py": A_LINES}, mtime=5000.0))
    assert coverage.is_stale("src/a.py", 2000.0)


def test_the_place_of_a_report_helps_to_match_a_bare_name():
    coverage = Coverage.build(ROOT, ("a/src/Shared.java", "b/src/Shared.java"),
                              [LoadedReport(ROOT / "b/build/jacoco.xml", 1.0, Report("JaCoCo", {"Shared.java": A_LINES}))])
    assert coverage.lines_of("b/src/Shared.java") == A_LINES


def test_load_reports_keeps_the_ones_that_read_and_tells_why_the_others_did_not(tmp_path):
    write_files(tmp_path, {"lcov.info": "SF:a.js\nDA:1,1\nend_of_record\n", "coverage.xml": "<html/>"})
    reports, errors = load_reports([tmp_path / "lcov.info", tmp_path / "coverage.xml", tmp_path / "gone.info"])
    assert [report.report.format for report in reports] == ["LCOV"] and reports[0].mtime > 0
    assert len(errors) == 2 and errors[0].startswith("coverage.xml") and errors[1].startswith("gone.info")


def test_the_shares_of_all_files_and_directories_can_be_listed_for_the_tree():
    coverage = build(loaded({"src/a.py": A_LINES, "src/sub/c.py": {1: CoverageLine(1)}, "lib/d.py": {}}))
    assert coverage.file_percents() == {"src/a.py": 50.0, "src/sub/c.py": 100.0}
    assert coverage.directory_percents() == {"src": 100 * 3 / 5, "src/sub": 100.0}
