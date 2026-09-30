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


import heapq
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import chain, islice

BASENAME_PREFIX = 400
BASENAME_SUBSTRING = 300
PATH_SUBSTRING = 200
SCATTERED = 50
RECENT_BONUS = 30
CACHED_QUERIES = 16


@dataclass(frozen=True)
class Match:
    path: str
    positions: tuple[int, ...]


# A regular expression such as a.*?b.*?c backtracks badly when the last
# character is missing, and this runs for every path on every keystroke.
def _scattered(term: str, lower: str) -> bool:
    position = 0
    for char in term:
        position = lower.find(char, position) + 1
        if position == 0:
            return False
    return True


def _term_score(lower: str, basename_start: int, term: str) -> int | None:
    index = lower.find(term, basename_start)
    if index == basename_start:
        return BASENAME_PREFIX
    if index > basename_start:
        return BASENAME_SUBSTRING - min(index - basename_start, 50)
    index = lower.find(term)
    if index >= 0:
        return PATH_SUBSTRING - min(index, 100)
    return SCATTERED if _scattered(term, lower) else None


def _score(lower: str, terms: Sequence[str]) -> int | None:
    basename_start = lower.rfind("/") + 1
    total = 0
    for term in terms:
        score = _term_score(lower, basename_start, term)
        if score is None:
            return None
        total += score
    return total


def _positions(lower: str, terms: Sequence[str]) -> tuple[int, ...]:
    basename_start = lower.rfind("/") + 1
    marked: set[int] = set()
    for term in terms:
        index = lower.find(term, basename_start)
        if index < 0:
            index = lower.find(term)
        if index >= 0:
            marked.update(range(index, index + len(term)))
            continue
        cursor = 0
        for char in term:
            cursor = lower.index(char, cursor)
            marked.add(cursor)
            cursor += 1
    return tuple(sorted(marked))


# Names, unlike paths, may repeat, so what comes back are indices into the
# list, best first, each with the characters that matched.
def rank(names: Sequence[str], query: str, limit: int = 100) -> list[tuple[int, tuple[int, ...]]]:
    return rank_counted(names, query, limit)[0]


# The same, with the number of names that matched, however many the limit cut off.
def rank_counted(names: Sequence[str], query: str, limit: int = 100) -> tuple[list[tuple[int, tuple[int, ...]]], int]:
    terms = query.lower().split()
    if not terms:
        return [(index, ()) for index in range(min(limit, len(names)))], len(names)
    scored = [(-total, len(name), index) for index, name in enumerate(names)
              if (total := _score(name.lower(), terms)) is not None]
    best = [(index, _positions(names[index].lower(), terms)) for _, _, index in heapq.nsmallest(limit, scored)]
    return best, len(scored)


class PathMatcher:
    def __init__(self, paths: Sequence[str]) -> None:
        self._paths = tuple(paths)
        self._lower = [path.lower() for path in self._paths]
        self._known = frozenset(self._paths)
        self._pools: OrderedDict[str, list[int]] = OrderedDict()

    def search(self, query: str, recent: Sequence[str] = (), limit: int = 100) -> list[Match]:
        terms = query.lower().split()
        if not terms:
            return self._unfiltered(recent, limit)
        scored = [(index, score) for index in self._pool_for(" ".join(terms))
                  if (score := _score(self._lower[index], terms)) is not None]
        self._remember(" ".join(terms), [index for index, _ in scored])
        rank = {path: position for position, path in enumerate(recent)}
        best = heapq.nsmallest(limit, ((-(score + self._bonus(index, rank)), len(self._paths[index]),
                                        self._paths[index]) for index, score in scored))
        return [Match(path, _positions(path.lower(), terms)) for _, _, path in best]

    def _unfiltered(self, recent: Sequence[str], limit: int) -> list[Match]:
        first = [path for path in dict.fromkeys(recent) if path in self._known]
        listed = set(first)
        rest = (path for path in self._paths if path not in listed)
        return [Match(path, ()) for path in islice(chain(first, rest), limit)]

    def _bonus(self, index: int, rank: dict[str, int]) -> int:
        position = rank.get(self._paths[index])
        return 0 if position is None else max(1, RECENT_BONUS - position)

    # Whatever matches a longer query also matches every query it starts with,
    # so typing narrows the previous result instead of rescanning every path.
    def _pool_for(self, query: str) -> Sequence[int]:
        prefixes = [known for known in self._pools if query.startswith(known)]
        return self._pools[max(prefixes, key=len)] if prefixes else range(len(self._paths))

    def _remember(self, query: str, indices: list[int]) -> None:
        self._pools[query] = indices
        self._pools.move_to_end(query)
        while len(self._pools) > CACHED_QUERIES:
            self._pools.popitem(last=False)
