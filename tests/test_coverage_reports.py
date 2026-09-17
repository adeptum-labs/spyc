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

import pytest

from repos import write_files
from spyc.coverage.model import CoverageLine, ReportError
from spyc.coverage.reports import MAX_DEPTH, find_reports, load_report, parse_report

LCOV = "TN:\nSF:a.js\nDA:1,1\nend_of_record\n"
GO = "mode: set\nx.com/a.go:1.1,2.1 1 1\n"
COBERTURA = '<?xml version="1.0"?>\n<!DOCTYPE coverage SYSTEM "http://cobertura.sourceforge.net/xml/coverage-04.dtd">\n' \
            '<coverage><packages><package><classes><class filename="a.py"><lines><line number="1" hits="1"/>' \
            '</lines></class></classes></package></packages></coverage>'
JACOCO = '<?xml version="1.0"?>\n<!DOCTYPE report PUBLIC "-//JACOCO//DTD Report 1.1//EN" "report.dtd">\n' \
         '<report name="x"><package name="p"><sourcefile name="A.java"><line nr="1" mi="0" ci="1"/></sourcefile>' \
         '</package></report>'


@pytest.mark.parametrize("text, format", [(LCOV, "LCOV"), (GO, "Go"), (COBERTURA, "Cobertura"), (JACOCO, "JaCoCo"),
                                          ("﻿  \n" + LCOV, "LCOV"), ("﻿" + JACOCO, "JaCoCo")])
def test_the_format_is_told_from_the_content_not_the_name(text, format):
    assert parse_report(text).format == format


@pytest.mark.parametrize("text", ["", "hello\n", "<html><body/></html>", "{\"json\": true}"])
def test_anything_else_is_not_a_coverage_report(text):
    with pytest.raises(ReportError):
        parse_report(text)


def test_a_report_is_read_from_a_file_and_a_missing_or_huge_one_is_an_error(tmp_path, monkeypatch):
    write_files(tmp_path, {"lcov.info": LCOV})
    assert load_report(tmp_path / "lcov.info").files == {"a.js": {1: CoverageLine(1)}}
    with pytest.raises(ReportError):
        load_report(tmp_path / "missing.info")
    monkeypatch.setattr("spyc.coverage.reports.MAX_REPORT_BYTES", 5)
    with pytest.raises(ReportError):
        load_report(tmp_path / "lcov.info")


def test_a_pipe_named_like_a_report_is_an_error_not_a_hang(tmp_path):
    os.mkfifo(tmp_path / "lcov.info")
    with pytest.raises(ReportError):
        load_report(tmp_path / "lcov.info")


def test_reports_are_found_by_their_usual_names_at_a_bounded_depth(tmp_path):
    deep = "/".join(["d"] * MAX_DEPTH)
    write_files(tmp_path, {
        "coverage.xml": "x", "coverage/lcov.info": "x", "target/site/jacoco/jacoco.xml": "x",
        "build/reports/jacoco/test/jacocoTestReport.xml": "x", "cover.out": "x", "unit.lcov": "x",
        "notes.txt": "x", "src/main.py": "x", f"{deep}/lcov.info": "x", f"{deep}/d/lcov.info": "x",
        "node_modules/pkg/lcov.info": "x", ".git/lcov.info": "x", ".venv/lib/coverage.xml": "x"})
    assert [path.relative_to(tmp_path).as_posix() for path in find_reports(tmp_path)] == [
        "cover.out", "coverage.xml", "unit.lcov", "coverage/lcov.info", "target/site/jacoco/jacoco.xml",
        "build/reports/jacoco/test/jacocoTestReport.xml", f"{deep}/lcov.info"]


def test_the_search_does_not_follow_links_to_directories(tmp_path):
    write_files(tmp_path, {"a/lcov.info": "x"})
    (tmp_path / "a" / "loop").symlink_to(tmp_path, target_is_directory=True)
    assert [path.name for path in find_reports(tmp_path)] == ["lcov.info"]


def test_a_huge_tree_is_given_up_on_after_a_bounded_number_of_entries(tmp_path, monkeypatch):
    write_files(tmp_path, {f"d{index}/lcov.info": "x" for index in range(20)})
    monkeypatch.setattr("spyc.coverage.reports.MAX_ENTRIES", 25)
    assert 0 < len(find_reports(tmp_path)) < 20
