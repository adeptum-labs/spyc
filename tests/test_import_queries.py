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
REQUIRED = {"c": {"include"}, "cpp": {"include"}, "rust": {"use", "mod"}, "go": {"spec", "operand", "field", "define"}, "java": {"package", "class", "path", "wildcard", "name"}, "kotlin": {"package", "class", "path", "wildcard", "name"},
            "python": {"path", "from"}, "javascript": {"path"}, "typescript": {"path"}, "tsx": {"path"}}


def test_the_languages_with_import_queries_are_the_ones_the_graph_reads_and_yaml_has_none():
    assert {language.id for language in WITH_IMPORTS} == {"c", "cpp", "go", "rust", "java", "kotlin", "python", "javascript", "typescript", "tsx"}
    assert load_imports(LANGUAGES_BY_ID["yaml"]) is None


@pytest.mark.parametrize("language", WITH_IMPORTS, ids=lambda language: language.id)
def test_every_import_query_compiles_and_has_the_captures_the_extraction_reads(language):
    ts_language, source = load_imports(language)
    compile_query(ts_language, source)
    assert REQUIRED[language.id] <= set(re.findall(r"@([\w.]+)", source))
