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


import posixpath
import re

TEST_DIRECTORIES = frozenset({"test", "tests", "__tests__", "spec", "specs"})
TEST_FILE = re.compile(r"(^test_.+\.py$|_test\.(py|go|rs|c|cpp|cc)$|^conftest\.py$|\.(test|spec)\.[jt]sx?$|Tests?\.(java|kt)$)")


# A file is a test by the directory it is in or by how it is named, as the build tools of each language expect.
def is_test_path(path: str) -> bool:
    directory, name = posixpath.split(path)
    return bool(TEST_DIRECTORIES.intersection(directory.split("/"))) or TEST_FILE.search(name) is not None
