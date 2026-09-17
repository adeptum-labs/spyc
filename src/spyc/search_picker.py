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


from collections.abc import Callable, Sequence
from pathlib import Path

from rich.text import Text

from spyc.document import Document, load_document
from spyc.picking import Item
from spyc.printable import printable
from spyc.search import MAX_HITS, Hit, SearchResult, search_text


# Searching many files takes a moment, so the picker asks this source from a
# worker thread and only once typing has paused.
class SearchSource:
    placeholder = "Search the text of the project  (alt+r: pattern, alt+w: whole word)"
    threaded = True
    debounce = 0.25

    def __init__(self, root: Path, paths: Callable[[], Sequence[str]], whole_word: bool = False) -> None:
        self._root, self._paths = root, paths
        self.regex, self.whole_word = False, whole_word
        self._query = ""
        self._result = SearchResult()

    def toggle_regex(self) -> None:
        self.regex = not self.regex

    def toggle_word(self) -> None:
        self.whole_word = not self.whole_word

    def mode_text(self) -> str:
        return ("regex" if self.regex else "literal") + (" · whole word" if self.whole_word else "")

    def summary(self) -> str:
        if self._result.error:
            return f"Bad pattern: {self._result.error}"
        if not self._query:
            return ""
        count = len(self._result.hits)
        if self._result.truncated:
            return f"{count}+ hits, the list is cut"
        return f"{count} hits" if count else "no hits"

    def search(self, query: str) -> list[Item]:
        self._query = query
        self._result = search_text(self._root, self._paths(), query, regex=self.regex, whole_word=self.whole_word,
                                   limit=MAX_HITS)
        return [Item(hit.path, self._label(hit, query), hit.line) for hit in self._result.hits]

    def preview(self, item: Item) -> Document | None:
        try:
            return load_document(self._root / item.key)
        except OSError:
            return None

    def _label(self, hit: Hit, query: str) -> Text:
        stripped = hit.text.lstrip()
        label = Text(printable(stripped), no_wrap=True, overflow="ellipsis")
        start = hit.column - (len(hit.text) - len(stripped))
        if not self.regex and start >= 0:
            label.stylize("bold yellow", start, start + len(query))
        label.append(f"  {printable(hit.path)}:{hit.line}", style="dim")
        return label
