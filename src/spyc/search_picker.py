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


import threading
from collections.abc import Callable, Sequence

from rich.text import Text

from spyc.core.cancellation import Cancellation
from spyc.core.document import Document
from spyc.core.picking import Item
from spyc.core.printable import printable
from spyc.core.source import FileSource
from spyc.search import MAX_HITS, Hit, SearchResult, search_text


# Searching many files takes a moment, so the picker asks this source from a
# worker thread, one search at a time, and only once typing has paused. A
# search that is no longer wanted is cancelled.
class SearchSource:
    placeholder = "Search the text of the project  (F2: pattern, F3: whole word)"
    threaded = True
    debounce = 0.25

    def __init__(self, source: FileSource, paths: Callable[[], Sequence[str]], whole_word: bool = False) -> None:
        self._source, self._paths = source, paths
        self.regex, self.whole_word = False, whole_word
        self._last = ("", SearchResult())
        self._lock = threading.Lock()
        self._cancellation = Cancellation()

    def toggle_regex(self) -> None:
        self.regex = not self.regex

    def toggle_word(self) -> None:
        self.whole_word = not self.whole_word

    def mode_text(self) -> str:
        return ("regex" if self.regex else "literal") + (" · whole word" if self.whole_word else "")

    def summary(self) -> str:
        query, result = self._last
        if result.error:
            return result.error
        if not query:
            return ""
        count = len(result.hits)
        if result.truncated:
            return f"{count}+ hits, the list is cut"
        return {0: "no hits", 1: "1 hit"}.get(count, f"{count} hits")

    def cancel(self) -> None:
        with self._lock:
            self._cancellation.cancel()

    def search(self, query: str) -> list[Item]:
        cancellation = Cancellation()
        with self._lock:
            self._cancellation = cancellation
        result = search_text(self._source.root, self._paths(), query, regex=self.regex, whole_word=self.whole_word,
                             limit=MAX_HITS, source=self._source, cancellation=cancellation)
        self._last = (query, result)
        return [Item(hit.path, self._label(hit, query), hit.line, hit.column) for hit in result.hits]

    def preview(self, item: Item) -> Document | None:
        try:
            return self._source.document(item.key)
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
