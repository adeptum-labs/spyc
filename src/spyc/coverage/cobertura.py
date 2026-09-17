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

from spyc.coverage.model import CoverageLine, Lines, Report, add_line
from spyc.coverage.safe_xml import parse_xml


def parse_cobertura(text: str) -> Report:
    root = parse_xml(text, "coverage")
    files: dict[str, Lines] = {}
    for coverage_class in root.iterfind("./packages/package/classes/class"):
        lines = files.setdefault(coverage_class.get("filename", ""), {})
        for element in coverage_class.iterfind("./lines/line"):
            _add_line(lines, element)
    return Report("Cobertura", {name: lines for name, lines in files.items() if name and lines},
                  tuple(source.text.strip() for source in root.iterfind("./sources/source") if source.text))


def _add_line(lines: Lines, element: Element) -> None:
    number, hits = element.get("number", ""), element.get("hits", "")
    if not number.isdigit() or not hits.isdigit():
        return
    partial = int(hits) > 0 and _misses_a_branch(element.get("condition-coverage", ""))
    add_line(lines, int(number), CoverageLine(int(hits), partial))


# "50% (1/2)": one of two conditions was taken.
def _misses_a_branch(condition_coverage: str) -> bool:
    taken, _, total = condition_coverage.partition("(")[2].rstrip(")").partition("/")
    return taken.isdigit() and total.isdigit() and int(taken) < int(total)
