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

from spyc.coverage.jacoco import parse_jacoco
from spyc.coverage.model import CoverageLine, ReportError

SAMPLE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<!DOCTYPE report PUBLIC "-//JACOCO//DTD Report 1.1//EN" "report.dtd">
<report name="demo">
  <package name="com/acme">
    <class name="com/acme/Foo" sourcefilename="Foo.java"><method name="f" desc="()V" line="3"/></class>
    <sourcefile name="Foo.java">
      <line nr="3" mi="0" ci="4" mb="0" cb="0"/>
      <line nr="4" mi="2" ci="0" mb="0" cb="0"/>
      <line nr="5" mi="1" ci="3" mb="1" cb="1"/>
      <line nr="6" mi="0" ci="2" mb="0" cb="2"/>
      <counter type="LINE" missed="1" covered="3"/>
    </sourcefile>
  </package>
  <package name="">
    <sourcefile name="Main.kt"><line nr="1" mi="0" ci="1" mb="0" cb="0"/></sourcefile>
  </package>
</report>
"""


def test_a_line_is_missed_covered_or_partial_by_its_instructions_and_branches():
    report = parse_jacoco(SAMPLE)
    assert report.format == "JaCoCo"
    assert report.files == {
        "com/acme/Foo.java": {3: CoverageLine(4), 4: CoverageLine(0), 5: CoverageLine(3, partial=True),
                              6: CoverageLine(2)},
        "Main.kt": {1: CoverageLine(1)}}


def test_lines_without_any_instruction_and_broken_numbers_are_skipped():
    text = '<report><package name="p"><sourcefile name="A.java"><line nr="1" mi="0" ci="0"/>' \
           '<line nr="x" mi="1" ci="0"/><line nr="2" mi="1" ci="0"/></sourcefile></package></report>'
    assert parse_jacoco(text).files == {"p/A.java": {2: CoverageLine(0)}}


@pytest.mark.parametrize("text", ["nope", "<coverage/>", '<!DOCTYPE r [<!ENTITY a "b">]><report>&a;</report>'])
def test_text_that_is_not_a_safe_jacoco_report_is_an_error(text):
    with pytest.raises(ReportError):
        parse_jacoco(text)
