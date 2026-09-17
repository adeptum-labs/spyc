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

from spyc.coverage.cobertura import parse_cobertura
from spyc.coverage.model import CoverageLine, ReportError

SAMPLE = """<?xml version="1.0"?>
<coverage line-rate="0.5" version="1">
  <sources><source>/work/project</source><source>lib</source></sources>
  <packages>
    <package name="pkg">
      <classes>
        <class name="pkg.b" filename="pkg/b.py">
          <methods>
            <method name="f" signature="()"><lines><line number="1" hits="9"/></lines></method>
          </methods>
          <lines>
            <line number="1" hits="1" branch="false"/>
            <line number="2" hits="0"/>
            <line number="3" hits="4" branch="true" condition-coverage="50% (1/2)"/>
            <line number="4" hits="2" branch="true" condition-coverage="100% (2/2)"/>
          </lines>
        </class>
        <class name="pkg.b2" filename="pkg/b.py">
          <lines><line number="2" hits="3"/></lines>
        </class>
        <class name="pkg.c" filename="pkg/c.py"><lines><line number="8" hits="0"/></lines></class>
      </classes>
    </package>
  </packages>
</coverage>
"""


def test_the_lines_of_each_class_are_read_and_classes_of_a_file_are_merged():
    report = parse_cobertura(SAMPLE)
    assert report.format == "Cobertura"
    assert report.files == {
        "pkg/b.py": {1: CoverageLine(1), 2: CoverageLine(3), 3: CoverageLine(4, partial=True), 4: CoverageLine(2)},
        "pkg/c.py": {8: CoverageLine(0)}}


def test_the_source_roots_are_kept_for_resolving_the_paths():
    assert parse_cobertura(SAMPLE).source_roots == ("/work/project", "lib")


@pytest.mark.parametrize("text", ["not xml at all", "<coverage><packages>", "<report/>",
                                  '<!DOCTYPE c [<!ENTITY a "aaaa">]><coverage>&a;</coverage>'])
def test_text_that_is_not_a_safe_cobertura_report_is_an_error(text):
    with pytest.raises(ReportError):
        parse_cobertura(text)


def test_a_line_without_a_number_or_hits_is_skipped():
    text = '<coverage><packages><package><classes><class filename="a.py"><lines>' \
           '<line number="x" hits="1"/><line hits="1"/><line number="2"/><line number="3" hits="1"/>' \
           '</lines></class></classes></package></packages></coverage>'
    assert parse_cobertura(text).files == {"a.py": {3: CoverageLine(1)}}
