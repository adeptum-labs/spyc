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


import importlib
import logging
import warnings
from functools import cache
from importlib import resources

from tree_sitter import Language as TreeSitterLanguage

from spyc.languages import Language

log = logging.getLogger(__name__)


# A wheel built for another ABI or a missing package must not stop a file from
# showing, so any failure here means "no grammar" and Pygments takes over.
@cache
def load_grammar(language: Language) -> tuple[TreeSitterLanguage, str] | None:
    if language.grammar is None:
        return None
    module, function = language.grammar
    try:
        # The SCSS wheel still hands over its grammar as an int, which py-tree-sitter accepts but warns about.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            ts_language = TreeSitterLanguage(getattr(importlib.import_module(module), function)())
        query = "\n".join(resources.files(package).joinpath(path).read_text(encoding="utf-8")
                          for package, path in language.highlights)
    except Exception as error:
        log.warning("No tree-sitter grammar for %s: %s", language.id, error)
        return None
    return ts_language, query
