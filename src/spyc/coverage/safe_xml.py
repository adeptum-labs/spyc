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


from xml.etree.ElementTree import Element, ParseError

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from spyc.coverage.model import ReportError


# Reports come from any build, so entities and external references are refused.
def parse_xml(text: str, root_tag: str) -> Element:
    try:
        root = ElementTree.fromstring(text)
    except (ParseError, DefusedXmlException) as error:
        raise ReportError(f"Not a readable {root_tag} report: {error}") from error
    if root.tag != root_tag:
        raise ReportError(f"Expected <{root_tag}>, found <{root.tag}>")
    return root
