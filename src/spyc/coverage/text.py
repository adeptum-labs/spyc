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


from rich.text import Text

from spyc.coverage.index import Coverage

GOOD = 80
FAIR = 50


# Cut down, never rounded up: 99.6% must not read as covered in full.
def percent_text(percent: float) -> str:
    return f"{int(percent)}%"


def percent_style(percent: float) -> str:
    return "green" if percent >= GOOD else "yellow" if percent >= FAIR else "red"


def summary_text(coverage: Coverage) -> Text:
    covered, total = coverage.total
    if not total:
        return Text()
    text = Text(f"Coverage {percent_text(100 * covered / total)}", style=percent_style(100 * covered / total))
    text.append(f" · {covered:,} of {total:,} lines · {', '.join(coverage.formats)}\n")
    if coverage.unmatched:
        many = coverage.unmatched != 1
        text.append(f"{coverage.unmatched:,} file{'s' if many else ''} of the reports {'are' if many else 'is'} "
                    "not in the project\n", style="yellow")
    return text


def coverage_status(percent: float, stale: bool) -> str:
    return f"coverage {percent_text(percent)}" + (" (stale)" if stale else "")
