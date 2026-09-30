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
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

from spyc.core.languages import LANGUAGES

ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = "usr/lib/spyc"
DEB_REVISION = 1
# The bundle carries Debian 12's libexpat, which needs glibc 2.36.
DEPENDS = "libc6 (>= 2.36), git"
RECOMMENDS = "ripgrep"
LONG_DESCRIPTION = (
    "Shows a code base in the terminal: the files as a tree, the code colored",
    "with tree-sitter, history and blame from git, search, outline and",
    "go-to-definition, and coverage from LCOV, Cobertura, JaCoCo and Go reports.",
)
COPYRIGHT = """\
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: spyc
Upstream-Contact: info@adeptum.se

Files: *
Copyright: 2026 Adam Waldenberg, Adeptum AB
License: GPL-3+
 On Debian systems, the full text of the GNU General Public License
 version 3 can be found in /usr/share/common-licenses/GPL-3.
"""


def project_metadata(pyproject: Path = ROOT / "pyproject.toml") -> dict:
    return tomllib.loads(pyproject.read_text())["project"]


# A development version sorts before the release it leads up to, as ~ does in Debian versions.
def debian_version(version: str) -> str:
    return re.sub(r"\.dev(\d+)$", r"~dev\1", version)


def control_text(project: dict, arch: str) -> str:
    author = project["authors"][0]
    header = [
        "Package: spyc",
        f"Version: {debian_version(project['version'])}-{DEB_REVISION}",
        f"Architecture: {arch}",
        "Section: devel",
        "Priority: optional",
        f"Depends: {DEPENDS}",
        f"Recommends: {RECOMMENDS}",
        f"Maintainer: {author['name']} <{author['email']}>",
        f"Description: {project['description']}",
    ]
    return "\n".join([*header, *(f" {line}" for line in LONG_DESCRIPTION), ""])


def assemble(tree: Path, bundle: Path, project: dict, arch: str) -> None:
    shutil.copytree(bundle, tree / LIB_DIR, symlinks=True)
    binaries = tree / "usr/bin"
    binaries.mkdir(parents=True)
    (binaries / "spyc").symlink_to("../lib/spyc/spyc")
    docs = tree / "usr/share/doc/spyc"
    docs.mkdir(parents=True)
    (docs / "copyright").write_text(COPYRIGHT)
    debian = tree / "DEBIAN"
    debian.mkdir()
    (debian / "control").write_text(control_text(project, arch))
    normalise_modes(tree)


# dpkg-deb keeps the modes it finds, so a group-writable file made under a
# different umask would be installed that way, and one made under 077 refused.
def normalise_modes(tree: Path) -> None:
    for path in (tree, *tree.rglob("*")):
        if not path.is_symlink():
            path.chmod(0o755 if path.is_dir() or path.stat().st_mode & 0o100 else 0o644)


# The bundle is built for the machine it runs on, so the label comes from the
# machine rather than from an argument that could disagree with it.
def host_architecture(run=subprocess.run) -> str:
    return run(["dpkg", "--print-architecture"], capture_output=True, text=True, check=True).stdout.strip()


def distribution_name(requirement: str) -> str:
    return re.match(r"[A-Za-z0-9_.-]+", requirement)[0]


# The grammars are imported by name at run time, which PyInstaller's static
# analysis cannot see, so each one is collected whole, with its native library
# and queries. The same goes for the Pygments lexers and for Textual and rich.
# The metadata of spyc and of the tree-sitter packages is what the version
# flag and the cache of definitions read.
def pyinstaller_command(work: Path, onefile: bool, project: dict | None = None) -> list[str]:
    project = project or project_metadata()
    grammars = sorted({language.grammar[0] for language in LANGUAGES if language.grammar})
    tree_sitter = [name for name in map(distribution_name, project["dependencies"]) if name.startswith("tree-sitter")]
    return [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile" if onefile else "--onedir", "--name", "spyc",
        "--distpath", str(work / "dist"), "--workpath", str(work / "build"), "--specpath", str(work),
        "--add-data", f"{ROOT / 'src/spyc/syntax/queries'}:spyc/syntax/queries",
        "--collect-all", "textual",
        "--collect-all", "tree_sitter",
        *(flag for module in grammars for flag in ("--collect-all", module)),
        "--collect-submodules", "rich",
        "--collect-submodules", "pygments",
        "--copy-metadata", "spyc",
        *(flag for name in tree_sitter for flag in ("--copy-metadata", name)),
        str(ROOT / "packaging/entry.py"),
    ]


# The result is a directory of files, or a single executable with onefile.
def build_bundle(work: Path, onefile: bool = False) -> Path:
    subprocess.run(pyinstaller_command(work, onefile), check=True)
    return work / "dist" / "spyc"


def main() -> int:
    project, arch = project_metadata(), host_architecture()
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    deb = output / f"spyc_{project['version']}-{DEB_REVISION}_{arch}.deb"
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        assemble(work / "tree", build_bundle(work), project, arch)
        subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(work / "tree"), str(deb)], check=True)
    print(deb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
