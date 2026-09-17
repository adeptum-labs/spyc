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


from xml.etree.ElementTree import Element

from spyc.coverage.model import CoverageLine, Lines, Report, number_of
from spyc.coverage.safe_xml import parse_xml


# JaCoCo counts instructions and branches per line: a line ran if any of its
# instructions did, and is partial, yellow in JaCoCo's own reports, if some of
# its instructions or branches did not. An aggregated report keeps its packages
# in groups, at any depth.
def parse_jacoco(text: str) -> Report:
    files: dict[str, Lines] = {}
    for package in parse_xml(text, "report").iter("package"):
        for source in package.iterfind("./sourcefile"):
            lines = _lines_of(source)
            if lines:
                files[f"{package.get('name')}/{source.get('name')}".lstrip("/")] = lines
    return Report("JaCoCo", files)


def _lines_of(source: Element) -> Lines:
    lines: Lines = {}
    for element in source.iterfind("./line"):
        number, missed, covered = (number_of(element.get(name, "")) for name in ("nr", "mi", "ci"))
        missed_branches = number_of(element.get("mb", "")) or 0
        if None not in (number, missed, covered) and missed + covered > 0:
            lines[number] = CoverageLine(covered, covered > 0 and (missed > 0 or missed_branches > 0))
    return lines
