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


import pytest

from spyc.deps.testfiles import is_test_path


@pytest.mark.parametrize("path", [
    "src/test/java/com/acme/OrderTest.java", "tests/test_app.py", "pkg/test_util.py", "pkg/util_test.py", "conftest.py",
    "web/src/app.test.ts", "web/src/app.spec.tsx", "internal/db/db_test.go", "src/__tests__/a.js", "src/OrderTests.kt",
])
def test_a_file_in_a_test_directory_or_named_like_a_test_is_a_test(path):
    assert is_test_path(path)


@pytest.mark.parametrize("path", [
    "src/main/java/com/acme/Order.java", "src/spyc/app.py", "pkg/contest.py", "web/src/latest.ts", "src/Attestation.java",
    "pkg/testing_utils.py",
])
def test_any_other_file_is_not(path):
    assert not is_test_path(path)
