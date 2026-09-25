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


from tree_sitter import Parser, Query

from spyc.deps.extract import MAX_IMPORTS, MAX_USED, facts_of
from spyc.deps.facts import ClassDef, Import
from spyc.languages import LANGUAGES_BY_ID
from spyc.syntax.grammars import load_imports

JAVA = """package com.acme.order;

import java.util.List;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.*;
import com.acme.model.*;
import com.acme.model.Order.Line;

public class OrderService extends BaseService {
    private final Repo repo;
    Money money = Money.zero();
}
interface Auditable {}
enum Kind { A }
record Pair(int a) {}
"""
KOTLIN = """package com.acme.order

import com.acme.model.Order
import com.acme.model.*
import com.acme.util.Money as M

class OrderService(private val repo: Repo) : BaseService() {
    fun find(id: Long): Order? { val m: M = M.zero(); return repo.get(id) }
}
object Registry
interface Auditable
fun helper() {}
"""


def facts(language_id, source):
    ts_language, query = load_imports(LANGUAGES_BY_ID[language_id])
    tree = Parser(ts_language).parse(source.encode("utf-8"))
    return facts_of(tree, Query(ts_language, query))


def test_java_gives_the_package_the_top_level_types_the_imports_and_the_capitalised_names():
    result = facts("java", JAVA)
    assert result.unit == "com.acme.order"
    assert result.classes == (ClassDef("OrderService", 9), ClassDef("Auditable", 13), ClassDef("Kind", 14), ClassDef("Pair", 15))
    assert result.imports == (
        Import("java.util.List"), Import("org.junit.Assert.assertEquals", static=True),
        Import("org.junit.Assert", wildcard=True, static=True), Import("com.acme.model", wildcard=True),
        Import("com.acme.model.Order.Line"))
    assert result.used == {"A", "Assert", "Auditable", "BaseService", "Kind", "Line", "List", "Money", "Order",
                           "OrderService", "Pair", "Repo"}


def test_kotlin_gives_the_same_facts_and_leaves_top_level_functions_out_of_the_classes():
    result = facts("kotlin", KOTLIN)
    assert result.unit == "com.acme.order"
    assert result.classes == (ClassDef("OrderService", 7), ClassDef("Registry", 10), ClassDef("Auditable", 11))
    assert result.imports == (Import("com.acme.model.Order"), Import("com.acme.model", wildcard=True),
                              Import("com.acme.util.Money"))
    assert {"Order", "Money", "M", "Repo", "BaseService"} <= result.used and "helper" not in result.used


def test_a_file_without_a_package_line_is_in_the_default_unit():
    result = facts("java", "public class Main { }\n")
    assert result.unit == "" and result.classes == (ClassDef("Main", 1),)


def test_source_that_does_not_parse_still_gives_what_does():
    result = facts("java", "package a.b;\nimport x.Y;\nclass Broken {{{ ((( \n")
    assert result.unit == "a.b" and result.imports == (Import("x.Y"),)


def test_invalid_utf8_and_control_characters_in_names_do_not_stop_the_extraction():
    source = "package a.b;\nimport x.Y;\nclass C { String s = \"\x1b[2J\"; }\n".encode("utf-8") + b"\n// \xff\xfe\n"
    ts_language, query = load_imports(LANGUAGES_BY_ID["java"])
    result = facts_of(Parser(ts_language).parse(source), Query(ts_language, query))
    assert result.unit == "a.b" and result.classes == (ClassDef("C", 3),)


def test_a_file_with_thousands_of_imports_is_capped():
    source = "package a.b;\n" + "".join(f"import p{index}.C{index};\n" for index in range(MAX_IMPORTS + 100))
    result = facts("java", source)
    assert len(result.imports) == MAX_IMPORTS and len(result.used) == MAX_USED


def test_a_file_with_thousands_of_classes_keeps_only_the_first_ones():
    from spyc.deps.extract import MAX_CLASSES
    result = facts("java", "".join(f"class C{index} {{}}\n" for index in range(MAX_CLASSES + 50)))
    assert len(result.classes) == MAX_CLASSES and result.classes[0] == ClassDef("C0", 1)


PYTHON = """import os, a.b as c
from . import x
from ..pkg.mod import y as z, w
from a.b import *
from .m import n
from p import (q, r)
"""


def test_python_imports_give_the_module_the_dots_and_the_names_and_a_wildcard():
    assert facts("python", PYTHON).imports == (
        Import("os"), Import("a.b"), Import("", level=1, names=("x",)),
        Import("pkg.mod", level=2, names=("y", "w")), Import("a.b", wildcard=True), Import("m", level=1, names=("n",)),
        Import("p", names=("q", "r")))


def test_python_facts_have_no_package_and_no_classes():
    result = facts("python", "import os\nclass A: pass\n")
    assert result.unit == "" and result.classes == () and result.used == frozenset()


JAVASCRIPT = """import a from './a';
import {b} from "../b.js";
export * from './c';
export {d} from './d';
const e = require('./e');
const f = await import('./f');
import './side';
foo('./nope');
require(dynamicName);
const g = require('pkg');
"""
TYPESCRIPT = """import type {T} from './t';
import x = require('./x');
export type {U} from './u';
import('./v');
"""


def test_javascript_gives_every_import_export_from_require_and_dynamic_import_with_a_literal():
    assert [imported.path for imported in facts("javascript", JAVASCRIPT).imports] == [
        "./a", "../b.js", "./c", "./d", "./e", "./f", "./side", "pkg"]


def test_typescript_and_tsx_give_the_same_and_the_forms_of_typescript():
    assert [imported.path for imported in facts("typescript", TYPESCRIPT).imports] == ["./t", "./x", "./u", "./v"]
    assert [imported.path for imported in facts("tsx", "import React from 'react';\nimport {A} from './A';\n").imports] == ["react", "./A"]


def test_script_facts_have_no_package_classes_or_used_names():
    result = facts("javascript", "import a from './a';\nclass A {}\n")
    assert (result.unit, result.classes, result.used) == ("", (), frozenset())


GO = """package main

import (
    "fmt"
    str "strings"
    . "example.com/dot"
    _ "example.com/blank"
    "example.com/mod/pkg/api/v2"
    "gopkg.in/yaml.v3"
)
import "os"

func Run() { fmt.Println(str.ToUpper("x")); api.Do(); yaml.Marshal(1) }
type T struct{}
type ( A int; B string )
type Alias = int
const C = 1
const ( D = 1; E = 2 )
var V, W = 2, 3
var ( X = 1; Y = 2 )
func (t T) M() {}
"""


def test_go_imports_carry_the_names_used_through_them_and_dot_imports_are_wildcards():
    result = facts("go", GO)
    assert [(imported.path, imported.wildcard, imported.names) for imported in result.imports] == [
        ("fmt", False, ("Println",)), ("strings", False, ("ToUpper",)), ("example.com/dot", True, ()),
        ("example.com/blank", False, ()), ("example.com/mod/pkg/api/v2", False, ("Do",)),
        ("gopkg.in/yaml.v3", False, ("Marshal",)), ("os", False, ())]


def test_go_files_define_their_top_level_names_and_not_their_methods():
    result = facts("go", GO)
    assert result.defines == {"Run", "T", "A", "B", "Alias", "C", "D", "E", "V", "W", "X", "Y"}
    assert result.classes == ()


def test_a_go_file_with_thousands_of_imports_selectors_and_definitions_is_capped():
    source = ("package p\nimport (\n" + "".join(f'    a{index} "x.com/p{index}"\n' for index in range(MAX_IMPORTS + 50)) + ")\n"
              + "".join(f"const K{index} = 1\n" for index in range(MAX_USED + 50))
              + "func f() {\n" + "".join(f"    a0.N{index}()\n" for index in range(MAX_USED + 50)) + "}\n")
    result = facts("go", source)
    assert len(result.imports) == MAX_IMPORTS and len(result.defines) == MAX_USED
    assert len(result.imports[0].names) <= MAX_USED
