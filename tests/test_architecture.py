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


from pathlib import Path

import spyc
from spyc.deps.graph import FILE, UNIT, DependencyGraph, Node
from spyc.symbol_index import SymbolIndex


# spyc reads its own source with its own dependency graph: a package that imports a package that imports it back
# is a cycle that the code base has to live with, so it is not allowed to come back unnoticed.
def test_the_source_of_spyc_has_no_cyclic_directories_or_files(tmp_path):
    source = Path(spyc.__file__).parent.parent
    paths = tuple(sorted(path.relative_to(source).as_posix() for path in (source / "spyc").rglob("*.py")))
    index = SymbolIndex(source, tmp_path / "cache.json")
    index.update(paths)
    graph = DependencyGraph(index.facts())
    assert {link.node.key for link in graph.incoming(Node(UNIT, "spyc/core"))} >= {"spyc", "spyc/widgets", "spyc/screens"}
    assert [node.key for node in graph.cyclic_nodes(UNIT)] == []
    assert [node.key for node in graph.cyclic_nodes(FILE)] == []
