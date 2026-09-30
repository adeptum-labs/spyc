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


from spyc.core.tree_model import Entry, TreeModel

PATHS = ["README.md", "src/main/java/A.java", "src/main/java/B.java", "src/test/T.java", "docs/guide.md", "Zed.txt"]


def names(entries):
    return [entry.name for entry in entries]


def test_directories_come_first_and_names_sort_ignoring_case():
    assert names(TreeModel(PATHS).children("")) == ["docs", "src", "README.md", "Zed.txt"]
    assert names(TreeModel(["b.txt", "A.txt"]).children("")) == ["A.txt", "b.txt"]


def test_single_child_directory_chains_are_compacted():
    model = TreeModel(PATHS)
    assert model.children("src") == [Entry("main/java", "src/main/java", True), Entry("test", "src/test", True)]
    assert names(model.children("src/main/java")) == ["A.java", "B.java"]


def test_the_root_is_compacted_too():
    assert TreeModel(["only/inner/x.py"]).children("") == [Entry("only/inner", "only/inner", True)]


def test_directories_above_lists_what_to_expand():
    model = TreeModel(PATHS)
    assert [entry.path for entry in model.directories_above("src/main/java/A.java")] == ["src", "src/main/java"]
    assert model.directories_above("README.md") == []
    assert model.directories_above("missing/file.txt") == []


def test_an_empty_model_has_no_entries():
    assert TreeModel([]).children("") == []
