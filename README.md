# spyc

A terminal viewer for browsing code bases. It finds the project you point it at, shows an overview of it, lists the
files as a tree, colors the code, shows the history from git, and is meant to be the tool you open a code base with.

![A file with coverage marks in the margin, changed lines marked, and shares in the tree](docs/code.svg)

![The overview of a project](docs/overview.svg)

![The commit log with the diff of a commit](docs/log.svg)

## Requirements

- Python 3.11 or later, when installing from source
- `git` on the path (lists the files of a project and gives the history, changes and blame)
- `rg` (ripgrep) is optional: it makes the search of the whole project fast and is needed for pattern search; without
  it the files are read in Python and the search is literal

## Install

Each release has a Debian package and a single-file executable for `amd64` and `arm64`. They are built on Debian 12
and run on Debian 12 and later and on Ubuntu 24.04 and later (they need glibc 2.36), and need no Python.

```sh
sudo apt install ./spyc_0.1.0-1_amd64.deb     # brings git, and ripgrep as a recommendation
chmod +x spyc-linux-amd64 && ./spyc-linux-amd64   # or the executable, which needs only git
```

The executable unpacks itself into a temporary directory on each start, so it starts a little slower than the
installed package. From source, `pip install .` gives the `spyc` command.

## Usage

```sh
spyc                       # the current directory
spyc path/to/dir           # a directory
spyc path/to/file.py:42    # a file, opened at line 42
spyc --coverage lcov.info  # show what a coverage report says; may be given more than once
```

`spyc` opens at the root of the project that contains the path: the git top level, or else the nearest directory with
a build file such as `pom.xml`, `Cargo.toml`, `go.mod` or `pyproject.toml`. The overview shows the languages by size,
the build systems and the key files, such as the README, the build files, the CI configuration and the entry points.

## Keys

| Keys | What they do |
|---|---|
| `f` | Find a file by name; `name:line` jumps to a line |
| `s` | Search the text of the project (ripgrep when installed); `alt+r` or `F2` for a pattern, `alt+w` or `F3` for whole words |
| `o` | Outline: the definitions of the open file |
| `t` | Find a definition anywhere in the project |
| `d` | Go to the definition of the name under the cursor, the nearest first; `[` comes back |
| `/` | Find in the file; `n` and `N` step through the matches |
| `:` | Go to a line |
| `[` `]` | Back and forward through the files you have visited |
| `l` | Commit log; the diff of each commit beside it, `/` filters by message, `Enter` on a diff line opens it |
| `L` | History of the open file, following renames |
| `g` | All uncommitted changes, staged or not, and new files, as one diff |
| `b` | Show who last changed each line; `Enter` on a line opens that commit |
| `c` | Show or hide what the tests ran, from the coverage reports |
| `G` | Dependency graph: what the package, file or class in the middle depends on and what depends on it; `Enter` moves along an edge, `[` and `]` go a level up or down, `c` finds cycles, `o` opens the code |
| `e` | Edit in `$VISUAL` or `$EDITOR` at the cursor line |
| `p` | Copy `path:line` to the clipboard |
| `i` | Project overview |
| `\` | Show or hide the file tree |
| `.` | Show or hide files that git ignores |
| `R` | Read the file list again |
| `r` | Rendered or source view of a Markdown file |
| `Tab` | Switch between the tree and the code |
| `?` | The key reference |
| `q` | Quit |
| `↑` `↓` `j` `k`, `←` `→` | Move by line and by character |
| `Home` `End` | Start or end of the line |
| `PgUp` `PgDn` `Space`, `ctrl+u` `ctrl+d` | Move by page or half a page |
| `ctrl+Home` `ctrl+End` | Start or end of the file |
| `Enter` | Open the file in the tree; `←` and `→` close and open directories |
| `ctrl+p` | Command palette, where the color theme can be changed |

Outline and go-to-definition know the definitions of Python, Java, Kotlin, Go, Rust, JavaScript, TypeScript, C, C++,
Bash and Markdown headings.

In a git repository the tree marks changed files and their directories, the code view marks added, changed and
deleted lines in the margin, and the overview and the title tell the branch, the number of changes and the last
commit. The mouse works too: click to place the cursor, scroll to move.

## Dependencies

`G` draws the dependencies of the project around one node: the packages that depend on it on the left, the ones it depends
on on the right, with the number of files behind each edge and `⟲` for a package in a cycle with it. Down a level are the
files of a package and the classes of a file. Java and Kotlin are read: the edges come from imports and from classes of
the same package (or of a wildcard-imported package) that a file uses by name. What the project does not contain is
counted on the node, not drawn. Reflection, dependency injection and dynamic loading are invisible, and a variable that
shares its name with a class of the same package can add an edge that is not there.

## Coverage

spyc reads LCOV, Cobertura, JaCoCo XML and Go cover profiles. Reports are recognised by their content and looked for by
their usual names (`lcov.info`, `coverage.xml`, `jacoco.xml`, `jacocoTestReport.xml`, `cover.out` and so on) up to six
directories down, build output included; `--coverage FILE` names them instead. Several reports of a project are merged,
and a line counts as often as its most thorough report says. Reports are read whole, so one over 32 MB is skipped.

In the margin a filled circle (green) is a line that ran, a half one (yellow) a line where some branch was never taken,
and an empty one (red) a line that never ran. The status bar gives the share of the lines of the open file that ran,
and says `(stale)` when the file is newer than its report. The tree shows the share after each file and directory,
and the overview the total. `c` hides and shows the margin and the tree shares, and the choice is remembered. The
paths of a report may be relative, absolute in another checkout, Java package paths or Go import paths; they are
matched to the files of the project by their ends. Reports are read again with `R`.

## Colors

The code is colored with tree-sitter grammars for Bash, C, C++, CSS, Go, HTML, Java, JavaScript, JSON, Kotlin,
Python, Rust, SCSS, SQL, TOML, TSX, TypeScript, XML and YAML. Other languages are colored with Pygments. The theme
follows the one chosen in the command palette and is remembered.

## Files

`state.json` (recent files, theme, sidebar) and `spyc.log` (warnings) are kept in `$XDG_STATE_HOME/spyc`, by default
`~/.local/state/spyc`.

## License

Copyright © 2026 Adam Waldenberg, Adeptum AB. Licensed under the GNU General Public License, version 3 or later.
See [LICENSE](LICENSE).
