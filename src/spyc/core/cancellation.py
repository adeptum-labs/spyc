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
from collections.abc import Callable


# Lets a newer request stop an older one, also while the process behind it is busy and silent.
class Cancellation:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancelled = False
        self._kill: Callable[[], None] | None = None

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            kill = self._kill
        if kill is not None:
            kill()

    def on_cancel(self, kill: Callable[[], None]) -> None:
        with self._lock:
            self._kill = kill
            cancelled = self._cancelled
        if cancelled:
            kill()
