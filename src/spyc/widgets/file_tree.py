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


from rich.text import Text
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from spyc.tree_model import Entry, TreeModel


class FileTree(Tree[Entry]):
    BINDINGS = [
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
        Binding("right", "open_directory", show=False),
        Binding("left", "close_directory", show=False),
    ]

    class FileChosen(Message):
        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path

    def __init__(self, **kwargs) -> None:
        super().__init__("files", **kwargs)
        self.show_root = False
        self.guide_depth = 2
        self._model = TreeModel([])
        self._populated: set[int] = set()

    def load(self, model: TreeModel) -> None:
        self._model = model
        self._populated.clear()
        self.clear()
        self._populate(self.root)
        self.root.expand()
        if self.root.children:
            self.cursor_line = 0

    # Children are added when a directory is first opened, so a project with
    # hundreds of thousands of files costs only the rows that are visible.
    def _populate(self, node: TreeNode[Entry]) -> None:
        if node.id in self._populated:
            return
        self._populated.add(node.id)
        for entry in self._model.children(node.data.path if node.data else ""):
            label = Text(entry.name, style="bold" if entry.is_dir else "")
            if entry.is_dir:
                node.add(label, data=entry, allow_expand=True)
            else:
                node.add_leaf(label, data=entry)

    def on_tree_node_expanded(self, event: Tree.NodeExpanded[Entry]) -> None:
        self._populate(event.node)

    def on_tree_node_selected(self, event: Tree.NodeSelected[Entry]) -> None:
        if event.node.data is not None and not event.node.data.is_dir:
            self.post_message(self.FileChosen(event.node.data.path))

    def reveal(self, path: str) -> None:
        node: TreeNode[Entry] | None = self.root
        for directory in self._model.directories_above(path):
            node = self._child(node, directory.path)
            if node is None:
                return
            self._populate(node)
            node.expand()
        target = self._child(node, path)
        if target is not None:
            if target.allow_expand:
                self._populate(target)
                target.expand()
            # The visible lines are rebuilt lazily; the cursor needs the new line numbers.
            self._tree_lines
            self.move_cursor(target)

    @staticmethod
    def _child(node: TreeNode[Entry], path: str) -> TreeNode[Entry] | None:
        return next((child for child in node.children if child.data is not None and child.data.path == path), None)

    def action_open_directory(self) -> None:
        node = self.cursor_node
        if node is None:
            return
        if node.allow_expand and not node.is_expanded:
            node.expand()
        elif node.is_expanded and node.children:
            self.action_cursor_down()

    def action_close_directory(self) -> None:
        node = self.cursor_node
        if node is None:
            return
        if node.allow_expand and node.is_expanded:
            node.collapse()
        elif node.parent is not None and node.parent is not self.root:
            self.move_cursor(node.parent)
