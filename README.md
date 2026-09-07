# spyc

A terminal viewer for browsing code bases. It finds the project you point it at, shows an overview of it, lists the
files as a tree, colors the code, and is meant to be the tool you open a code base with.

## Requirements

- Python 3.11 or later
- `git` on the path (used to list the files of a project)

## Usage

```sh
pip install .
spyc                       # the current directory
spyc path/to/dir           # a directory
spyc path/to/file.py:42    # a file, opened at line 42
```

`spyc` opens at the root of the project that contains the path: the git top level, or else the nearest directory with
a build file such as `pom.xml`, `Cargo.toml`, `go.mod` or `pyproject.toml`. The overview shows the languages by size,
the build systems and the key files, such as the README, the build files, the CI configuration and the entry points.

## Keys

| Keys | What they do |
|---|---|
| `f` | Find a file by name; `name:line` jumps to a line |
| `/` | Find in the file; `n` and `N` step through the matches |
| `:` | Go to a line |
| `[` `]` | Back and forward through the files you have visited |
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

The mouse works too: click to place the cursor, scroll to move.

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
