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


import time

import pytest
from pygments.lexers import get_lexer_by_name

from spyc.languages import LANGUAGES, detect_language


@pytest.mark.parametrize("path, expected", [
    ("src/Main.java", "java"), ("build.gradle.kts", "kotlin"), ("web/page.xhtml", "xml"),
    ("app.properties", "properties"), ("App.tsx", "tsx"), ("lib.hpp", "cpp"), ("x.h", "c"),
    ("Dockerfile", "dockerfile"), ("Dockerfile.dev", "dockerfile"), ("CMakeLists.txt", "cmake"),
    ("Makefile", "make"), (".bashrc", "bash"), ("README.MD", "markdown"), ("Cargo.lock", "toml"),
])
def test_registry_languages_by_name_and_extension(path, expected):
    assert detect_language(path).id == expected


@pytest.mark.parametrize("first_line, expected", [
    ("#!/usr/bin/env python3.11", "python"),
    ("#!/bin/bash -e", "bash"),
    ("#!/usr/bin/env -S node --no-warnings", "javascript"),
])
def test_shebang_names_the_interpreter(first_line, expected):
    assert detect_language("bin/tool", first_line).id == expected


def test_unknown_extensions_fall_back_to_pygments():
    ruby = detect_language("script.rb")
    assert (ruby.name, ruby.grammar, ruby.lexer) == ("Ruby", None, "ruby")


def test_extensionless_files_are_recognised_by_exact_name_only():
    assert detect_language("Rakefile").name == "Ruby"
    assert detect_language("d41d8cd98f00b204e9800998ecf8427e") is None


def test_thousands_of_odd_file_names_are_classified_quickly():
    started = time.perf_counter()
    for number in range(20_000):
        detect_language(f"objects/{number:05d}abcdef")
    assert time.perf_counter() - started < 1.0


def test_plain_text_and_unknown_files_have_no_language():
    assert detect_language("notes.txt") is None
    assert detect_language("blob.qqq") is None


@pytest.mark.parametrize("language", [language for language in LANGUAGES if language.lexer],
                         ids=lambda language: language.id)
def test_every_fallback_lexer_exists(language):
    get_lexer_by_name(language.lexer)
