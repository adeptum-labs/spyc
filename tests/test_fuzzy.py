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

from spyc.fuzzy import PathMatcher, rank, rank_counted

PATHS = ["src/app.py", "src/application/main.py", "README.md", "docs/app-guide.md",
         "tests/test_app.py", "src/util/strings.py"]


def found(query, **arguments):
    return [match.path for match in PathMatcher(PATHS).search(query, **arguments)]


def test_a_basename_prefix_beats_a_basename_substring_beats_a_directory_hit():
    assert found("app") == ["src/app.py", "docs/app-guide.md", "tests/test_app.py", "src/application/main.py"]


def test_every_term_must_match():
    assert found("test app") == ["tests/test_app.py"]


def test_scattered_characters_match_as_a_last_resort():
    assert found("srcstr") == ["src/util/strings.py"]


def test_matching_ignores_case():
    assert found("readme") == ["README.md"]


def test_nothing_matches_gibberish():
    assert found("qqqq") == []


def test_the_limit_caps_the_results():
    assert len(found("app", limit=2)) == 2


def test_positions_mark_a_contiguous_hit():
    assert PathMatcher(PATHS).search("app")[0].positions == (4, 5, 6)


def test_positions_mark_scattered_characters_in_order():
    assert PathMatcher(PATHS).search("srcstr")[0].positions == (0, 1, 2, 9, 10, 11)


def test_an_empty_query_lists_recent_files_that_still_exist_then_the_rest():
    assert found("", recent=["gone.py", "tests/test_app.py", "README.md"]) == [
        "tests/test_app.py", "README.md", "src/app.py", "src/application/main.py", "docs/app-guide.md",
        "src/util/strings.py"]


def test_recent_files_win_ties():
    matcher = PathMatcher(["a/x_one.py", "b/x_two.py"])
    assert [match.path for match in matcher.search("x")] == ["a/x_one.py", "b/x_two.py"]
    assert [match.path for match in matcher.search("x", recent=["b/x_two.py"])] == ["b/x_two.py", "a/x_one.py"]


def test_typing_and_backspacing_gives_the_same_results_as_a_fresh_search():
    typed = PathMatcher(PATHS)
    for query in ("a", "ap", "app", "ap", "a"):
        assert typed.search(query) == PathMatcher(PATHS).search(query)


def test_a_query_that_almost_matches_every_path_stays_fast():
    paths = [("reader/" * 20) + f"{number}.txt" for number in range(20_000)]
    started = time.perf_counter()
    assert PathMatcher(paths).search("readm") == []
    assert time.perf_counter() - started < 2.0


def test_a_hundred_thousand_paths_are_searched_in_reasonable_time():
    paths = [f"module{number % 500}/package{number % 37}/file{number}.py" for number in range(100_000)]
    matcher = PathMatcher(paths)
    started = time.perf_counter()
    matcher.search("file9")
    matcher.search("file99")
    assert time.perf_counter() - started < 2.0


def test_names_are_ranked_with_every_duplicate_kept_apart():
    names = ["render", "prerender", "Render", "reader", "render"]
    assert [index for index, _ in rank(names, "render")] == [0, 2, 4, 1]


def test_ranking_marks_the_matched_characters_and_keeps_the_order_without_a_query():
    assert rank(["alpha", "beta"], "bt") == [(1, (0, 2))]
    assert rank(["alpha", "beta"], "") == [(0, ()), (1, ())]


def test_ranking_stops_at_the_limit():
    assert len(rank([f"name{number}" for number in range(50)], "name", limit=5)) == 5


def test_a_ranking_can_say_how_many_matched_beyond_the_limit():
    names = [f"name{number}" for number in range(50)] + ["other"]
    shown, matched = rank_counted(names, "name", limit=5)
    assert (len(shown), matched) == (5, 50)
    assert rank_counted(names, "", limit=5)[1] == 51
