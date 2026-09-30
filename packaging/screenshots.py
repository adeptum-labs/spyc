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


import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from spyc.app import SpycApp
from spyc.core.location import Location
from spyc.state import StateStore

DOCS = Path(__file__).resolve().parent.parent / "docs"
SIZE = (118, 34)
SAMPLE = Path(tempfile.gettempdir()) / "spyc-screenshots" / "orders"
FILES = {
    ".gitignore": "coverage/\n__pycache__/\n",
    "pyproject.toml": '[project]\nname = "orders"\nversion = "1.4.0"\n',
    "README.md": "# Orders\n\nPrices and carts for the web shop.\n",
    "src/orders/__init__.py": '"""Carts and prices."""\n',
    "src/orders/pricing.py": (
        "from decimal import Decimal\n\nTAX = Decimal('0.25')\n\n\n"
        "def with_tax(net: Decimal) -> Decimal:\n    return (net * (1 + TAX)).quantize(Decimal('0.01'))\n\n\n"
        "def discount(net: Decimal, percent: int) -> Decimal:\n    if percent < 0 or percent > 100:\n"
        "        raise ValueError('A discount is between 0 and 100 percent')\n    if percent == 0:\n"
        "        return net\n    return net * (100 - percent) / 100\n"),
    "src/orders/cart.py": (
        "from decimal import Decimal\n\nfrom orders.pricing import discount, with_tax\n\n\n"
        "class Cart:\n    def __init__(self) -> None:\n        self._lines: list[tuple[str, Decimal, int]] = []\n\n"
        "    def add(self, name: str, price: Decimal, quantity: int = 1) -> None:\n"
        "        self._lines.append((name, price, quantity))\n\n"
        "    def total(self, percent_off: int = 0) -> Decimal:\n"
        "        net = sum((price * quantity for _, price, quantity in self._lines), Decimal(0))\n"
        "        return with_tax(discount(net, percent_off))\n"),
    "tests/test_cart.py": (
        "from decimal import Decimal\n\nfrom orders.cart import Cart\n\n\n"
        "def test_a_cart_totals_its_lines_with_tax():\n    cart = Cart()\n    cart.add('Pen', Decimal('10'), 2)\n"
        "    assert cart.total() == Decimal('25.00')\n"),
}
COVERAGE = {
    "coverage/lcov.info": (
        "SF:src/orders/pricing.py\nDA:1,1\nDA:3,1\nDA:6,1\nDA:7,4\nDA:10,4\nDA:11,3\nDA:12,0\nDA:13,3\nDA:14,0\n"
        "BRDA:11,0,0,0\nBRDA:11,0,1,3\nend_of_record\n"
        "SF:src/orders/cart.py\nDA:1,1\nDA:3,1\nDA:6,1\nDA:7,1\nDA:8,1\nDA:10,3\nDA:11,3\nDA:13,4\nDA:14,4\nDA:15,4\n"
        "end_of_record\n"),
}
HISTORY = [
    ("Ada Lovelace", "2026-01-12T10:00:00", "Start the order library", [".gitignore", "pyproject.toml", "README.md", "src/orders/__init__.py"]),
    ("Grace Hopper", "2026-02-03T14:30:00", "Price a cart with tax", ["src/orders/pricing.py", "src/orders/cart.py"]),
    ("Ada Lovelace", "2026-03-20T09:15:00", "Test the cart total", ["tests/test_cart.py"]),
]


def git(root: Path, *arguments: str, **environment: str) -> None:
    subprocess.run(["git", "-C", str(root), *arguments], check=True, capture_output=True,
                   env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", **environment})


def make_project(root: Path) -> None:
    root.mkdir(parents=True)
    git(root, "init", "-q")
    for author, moment, message, names in HISTORY:
        for name in names:
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(FILES[name])
        git(root, "add", "-A")
        git(root, "-c", "user.name=" + author, "-c", "user.email=" + author.split()[0].lower() + "@example.org",
            "commit", "-q", "-m", message, GIT_AUTHOR_DATE=moment, GIT_COMMITTER_DATE=moment)
    (root / "src/orders/pricing.py").write_text(FILES["src/orders/pricing.py"].replace("percent == 0", "percent <= 0"))
    for name, text in COVERAGE.items():
        (root / name).parent.mkdir(exist_ok=True)
        (root / name).write_text(text)


async def capture(root: Path, state: Path) -> None:
    app = SpycApp(root, Location("src/orders/pricing.py", 12), StateStore(state / "state.json"))
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        app.save_screenshot(filename="code.svg", path=str(DOCS))
        await pilot.press("i")
        await settle(pilot)
        app.save_screenshot(filename="overview.svg", path=str(DOCS))
        await pilot.press("l")
        await settle(pilot)
        app.save_screenshot(filename="log.svg", path=str(DOCS))


async def settle(pilot) -> None:
    await pilot.app.workers.wait_for_complete()
    await pilot.pause(1.0)


def main() -> int:
    DOCS.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as state:
        shutil.rmtree(SAMPLE.parent, ignore_errors=True)
        make_project(SAMPLE)
        asyncio.run(capture(SAMPLE, Path(state)))
        shutil.rmtree(SAMPLE.parent)
    print("\n".join(str(path) for path in sorted(DOCS.glob("*.svg"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
