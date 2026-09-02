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


from dataclasses import dataclass


@dataclass(frozen=True)
class Place:
    path: str
    line: int


# Works like a browser's history: the entry being left is updated to the line
# the reader had reached, so going back and then forward returns to it.
class JumpHistory:
    def __init__(self, limit: int = 100) -> None:
        self._limit = limit
        self._places: list[Place] = []
        self._index = -1

    def navigate(self, leaving: Place | None, destination: Place) -> None:
        if leaving is not None:
            self._remember(leaving)
        del self._places[self._index + 1:]
        if not self._places or self._places[-1] != destination:
            self._places.append(destination)
        self._index = len(self._places) - 1
        if len(self._places) > self._limit:
            del self._places[0]
            self._index -= 1

    def back(self, current: Place) -> Place | None:
        if self._index <= 0:
            return None
        self._places[self._index] = current
        self._index -= 1
        return self._places[self._index]

    def forward(self, current: Place) -> Place | None:
        if self._index >= len(self._places) - 1:
            return None
        self._places[self._index] = current
        self._index += 1
        return self._places[self._index]

    def _remember(self, place: Place) -> None:
        if self._index >= 0:
            self._places[self._index] = place
        else:
            self._places.append(place)
            self._index = 0
