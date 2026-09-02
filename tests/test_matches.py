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


from spyc.matches import find_matches


def test_lowercase_query_ignores_case():
    assert find_matches(["Foo foo", "bar"], "foo") == [(0, 0, 3), (0, 4, 7)]


def test_uppercase_in_query_makes_it_case_sensitive():
    assert find_matches(["Foo foo"], "Foo") == [(0, 0, 3)]


def test_query_is_literal():
    assert find_matches(["a.b axb"], "a.b") == [(0, 0, 3)]


def test_empty_query_has_no_matches():
    assert find_matches(["abc"], "") == []
