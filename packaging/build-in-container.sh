#!/bin/sh
#
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
#
# Builds the Debian package and the single-file executable inside a debian:12
# container, so that the bundled binary needs no newer glibc than Debian 12
# provides. Run from the repository root.
# Debian's python3 is linked statically, and PyInstaller needs the shared
# libpython, which comes from libpython3.11.
set -eu
apt-get update -qq
apt-get install -y -qq python3 python3-venv libpython3.11 binutils
python3 -m venv /tmp/venv
/tmp/venv/bin/pip install --quiet pyinstaller .
/tmp/venv/bin/python packaging/build_deb.py
/tmp/venv/bin/python packaging/build_binary.py
