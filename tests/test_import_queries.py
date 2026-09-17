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


import re

import pytest

from spyc.languages import LANGUAGES, LANGUAGES_BY_ID
from spyc.syntax.grammars import load_imports
from spyc.syntax.tree_sitter_highlighter import compile_query

WITH_IMPORTS = [language for language in LANGUAGES if language.imports]
CAPTURES = {"package", "class", "path", "wildcard", "name"}


def test_java_and_kotlin_have_import_queries_and_python_has_none_yet():
    assert {language.id for language in WITH_IMPORTS} == {"java", "kotlin"}
    assert load_imports(LANGUAGES_BY_ID["python"]) is None


@pytest.mark.parametrize("language", WITH_IMPORTS, ids=lambda language: language.id)
def test_every_import_query_compiles_and_has_the_captures_the_extraction_reads(language):
    ts_language, source = load_imports(language)
    compile_query(ts_language, source)
    assert CAPTURES <= set(re.findall(r"@([\w.]+)", source))
