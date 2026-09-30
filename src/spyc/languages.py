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
from dataclasses import dataclass, replace
from functools import cache
from pathlib import PurePosixPath

from pygments.lexers import get_all_lexers, get_lexer_for_filename
from pygments.util import ClassNotFound


@dataclass(frozen=True)
class Language:
    id: str
    name: str
    extensions: tuple[str, ...] = ()
    filenames: tuple[str, ...] = ()
    interpreters: tuple[str, ...] = ()
    grammar: tuple[str, str] | None = None
    highlights: tuple[tuple[str, str], ...] = ()
    lexer: str | None = None
    tags: tuple[tuple[str, str], ...] = ()
    imports: tuple[tuple[str, str], ...] = ()


def grammar(package: str, function: str = "language", *queries: tuple[str, str]) -> dict:
    return {"grammar": (package, function), "highlights": queries or ((package, "queries/highlights.scm"),)}


JS_HIGHLIGHTS = ("tree_sitter_javascript", "queries/highlights.scm")
JSX_HIGHLIGHTS = ("tree_sitter_javascript", "queries/highlights-jsx.scm")
TS_HIGHLIGHTS = ("tree_sitter_typescript", "queries/highlights.scm")

JS_TAGS = ("tree_sitter_javascript", "queries/tags.scm")
TS_TAGS = ("tree_sitter_typescript", "queries/tags.scm")
OWN_TS_TAGS = ("spyc.syntax", "queries/typescript/tags.scm")
# Queries that find the definitions of a file, for the outline and for go-to-definition.
TAGS = {
    "python": (("tree_sitter_python", "queries/tags.scm"),),
    "java": (("tree_sitter_java", "queries/tags.scm"),),
    "go": (("tree_sitter_go", "queries/tags.scm"),),
    "rust": (("tree_sitter_rust", "queries/tags.scm"),),
    "c": (("tree_sitter_c", "queries/tags.scm"),),
    "cpp": (("tree_sitter_cpp", "queries/tags.scm"),),
    "javascript": (JS_TAGS,),
    "typescript": (TS_TAGS, JS_TAGS, OWN_TS_TAGS),
    "tsx": (TS_TAGS, JS_TAGS, OWN_TS_TAGS),
    "kotlin": (("spyc.syntax", "queries/kotlin/tags.scm"),),
    "bash": (("spyc.syntax", "queries/bash/tags.scm"),),
}
# Queries that find the package, the classes and the imports of a file, for the dependency graph.
IMPORTS = {
    "c": (("spyc.syntax", "queries/c/imports.scm"),),
    "cpp": (("spyc.syntax", "queries/cpp/imports.scm"),),
    "go": (("spyc.syntax", "queries/go/imports.scm"),),
    "java": (("spyc.syntax", "queries/java/imports.scm"),),
    "kotlin": (("spyc.syntax", "queries/kotlin/imports.scm"),),
    "python": (("spyc.syntax", "queries/python/imports.scm"),),
    "rust": (("spyc.syntax", "queries/rust/imports.scm"),),
    "javascript": (("spyc.syntax", "queries/javascript/imports.scm"),),
    "typescript": (("spyc.syntax", "queries/typescript/imports.scm"),),
    "tsx": (("spyc.syntax", "queries/typescript/imports.scm"),),
}

# A query that extends another comes first, because the first matching pattern wins.
_DEFINED = (
    Language("bash", "Bash", (".sh", ".bash", ".zsh"), (".bashrc", ".bash_profile", ".profile", ".zshrc", "PKGBUILD"),
             ("sh", "bash", "zsh", "dash", "ksh"), lexer="bash", **grammar("tree_sitter_bash")),
    Language("c", "C", (".c", ".h"), lexer="c", **grammar("tree_sitter_c")),
    Language("cargo", "Cargo manifest", (), ("Cargo.toml",), lexer="toml", **grammar("tree_sitter_toml")),
    Language("cmake", "CMake", (".cmake",), ("CMakeLists.txt",), lexer="cmake"),
    Language("cpp", "C++", (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".ipp"), lexer="cpp",
             **grammar("tree_sitter_cpp", "language", ("tree_sitter_cpp", "queries/highlights.scm"),
                       ("tree_sitter_c", "queries/highlights.scm"))),
    Language("css", "CSS", (".css",), lexer="css", **grammar("tree_sitter_css")),
    Language("dockerfile", "Dockerfile", (".dockerfile",), ("Dockerfile", "Containerfile"), lexer="docker"),
    Language("go", "Go", (".go",), lexer="go", **grammar("tree_sitter_go")),
    # Pygments would take go.mod for Modula-2.
    Language("gomod", "Go module", filenames=("go.mod",), lexer="text"),
    Language("groovy", "Groovy", (".groovy", ".gradle"), ("Jenkinsfile",), lexer="groovy"),
    Language("html", "HTML", (".html", ".htm"), lexer="html", **grammar("tree_sitter_html")),
    Language("java", "Java", (".java",), lexer="java", **grammar("tree_sitter_java")),
    Language("javascript", "JavaScript", (".js", ".mjs", ".cjs", ".jsx"), (), ("node", "nodejs"), lexer="javascript",
             **grammar("tree_sitter_javascript", "language", JSX_HIGHLIGHTS, JS_HIGHLIGHTS)),
    Language("json", "JSON", (".json", ".jsonc"), (".babelrc", ".eslintrc"), lexer="json", **grammar("tree_sitter_json")),
    Language("kotlin", "Kotlin", (".kt", ".kts"), lexer="kotlin",
             **grammar("tree_sitter_kotlin", "language", ("spyc.syntax", "queries/kotlin/highlights.scm"))),
    Language("make", "Makefile", (".mk",), ("Makefile", "GNUmakefile", "makefile"), lexer="make"),
    Language("markdown", "Markdown", (".md", ".markdown"), lexer="markdown"),
    Language("properties", "Properties", (".properties",), lexer="properties"),
    Language("python", "Python", (".py", ".pyi", ".pyw"), (), ("python",), lexer="python", **grammar("tree_sitter_python")),
    Language("rust", "Rust", (".rs",), lexer="rust", **grammar("tree_sitter_rust")),
    Language("scss", "SCSS", (".scss",), lexer="scss", **grammar("tree_sitter_scss", "language", ("tree_sitter_scss", "queries/highlights.scm"),
                       ("tree_sitter_css", "queries/highlights.scm"))),
    Language("sql", "SQL", (".sql",), lexer="sql", **grammar("tree_sitter_sql")),
    Language("toml", "TOML", (".toml",), ("Cargo.lock", "Pipfile", "poetry.lock"), lexer="toml", **grammar("tree_sitter_toml")),
    Language("tsx", "TSX", (".tsx",), lexer="typescript",
             **grammar("tree_sitter_typescript", "language_tsx", TS_HIGHLIGHTS, JSX_HIGHLIGHTS, JS_HIGHLIGHTS)),
    Language("typescript", "TypeScript", (".ts", ".mts", ".cts"), (), ("deno", "ts-node"), lexer="typescript",
             **grammar("tree_sitter_typescript", "language_typescript", TS_HIGHLIGHTS, JS_HIGHLIGHTS)),
    Language("xml", "XML", (".xml", ".xhtml", ".xsd", ".xsl", ".xslt", ".svg", ".fxml", ".wsdl", ".plist"), lexer="xml",
             **grammar("tree_sitter_xml", "language_xml", ("tree_sitter_xml", "queries/xml/highlights.scm"))),
    Language("yaml", "YAML", (".yml", ".yaml"), (".clang-format",), lexer="yaml", **grammar("tree_sitter_yaml")),
)
LANGUAGES = tuple(replace(language, tags=TAGS.get(language.id, ()), imports=IMPORTS.get(language.id, ()))
                  for language in _DEFINED)
LANGUAGES_BY_ID = {language.id: language for language in LANGUAGES}
GO_MODULE = LANGUAGES_BY_ID["gomod"]
CARGO_MANIFEST = LANGUAGES_BY_ID["cargo"]
BY_EXTENSION = {extension: language for language in LANGUAGES for extension in language.extensions}
BY_FILENAME = {filename: language for language in LANGUAGES for filename in language.filenames}
BY_INTERPRETER = {interpreter: language for language in LANGUAGES for interpreter in language.interpreters}
VERSION_SUFFIX = re.compile(r"[\d.]+$")


def detect_language(path: str, first_line: str = "") -> Language | None:
    name = PurePosixPath(path).name
    suffix = PurePosixPath(name).suffix.lower()
    return (BY_FILENAME.get(name) or BY_FILENAME.get(name.split(".", 1)[0]) or BY_EXTENSION.get(suffix)
            or _by_interpreter(first_line) or _pygments_language(_pygments_key(name, suffix)))


# Pygments matches a file name by scanning every lexer's patterns, which costs
# milliseconds. Names with an extension are looked up by that extension, which
# repeats; names without one only when a lexer names that file exactly.
def _pygments_key(name: str, suffix: str) -> str | None:
    if suffix:
        return f"x{suffix}"
    return name if name in _exact_pygments_names() else None


@cache
def _exact_pygments_names() -> frozenset[str]:
    return frozenset(pattern for _, _, patterns, _ in get_all_lexers() for pattern in patterns
                     if not any(char in pattern for char in "*?["))


def _by_interpreter(first_line: str) -> Language | None:
    if not first_line.startswith("#!"):
        return None
    words = first_line[2:].split()
    if words and PurePosixPath(words[0]).name == "env":
        words = [word for word in words[1:] if not word.startswith("-")]
    return BY_INTERPRETER.get(VERSION_SUFFIX.sub("", PurePosixPath(words[0]).name)) if words else None


# Pygments scans every lexer's filename patterns on each call, so the lookup
# is cached per extension; large trees would otherwise take seconds.
@cache
def _pygments_language(filename: str | None) -> Language | None:
    if filename is None:
        return None
    try:
        lexer = get_lexer_for_filename(filename)
    except ClassNotFound:
        return None
    if not lexer.aliases or lexer.aliases[0] == "text":
        return None
    return Language(lexer.aliases[0], lexer.name, lexer=lexer.aliases[0])
