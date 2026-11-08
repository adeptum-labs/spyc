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


from collections import defaultdict
from collections.abc import Hashable, Iterable, Mapping


# The edges the other way round: from what is used to what uses it.
def reversed_edges(edges: Mapping[Hashable, Iterable[Hashable]]) -> dict[Hashable, list[Hashable]]:
    users = defaultdict(list)
    for source, targets in edges.items():
        for target in targets:
            users[target].append(source)
    return users


# Everything that `start` reaches along `edges`, without `start` itself unless a cycle leads back to it. It walks
# with a stack of its own, as a chain of thousands of nodes would overflow the stack of the interpreter.
def reached(edges: Mapping[Hashable, Iterable[Hashable]], start: Hashable) -> frozenset:
    found, pending = set(), [start]
    while pending:
        for other in edges.get(pending.pop(), ()):
            if other not in found:
                found.add(other)
                pending.append(other)
    return frozenset(found)
