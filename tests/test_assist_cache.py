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


import json

import pytest

from spyc.assist.cache import MAX_ANSWERS, AnswerCache, Cached


def cached(text="Answer", content="abc", when=1000.0):
    return Cached(content, "sonnet", when, text)


def test_an_answer_that_was_put_is_got_back_also_by_another_cache_on_the_same_file(tmp_path):
    AnswerCache(tmp_path / "answers.json").put("file:a.py", cached())
    assert AnswerCache(tmp_path / "answers.json").get("file:a.py") == cached()


def test_an_answer_that_was_never_put_is_missing(tmp_path):
    cache = AnswerCache(tmp_path / "answers.json")
    assert cache.get("file:a.py") is None
    cache.put("file:b.py", cached())
    assert cache.get("file:a.py") is None


def test_putting_again_replaces_the_answer_and_keeps_the_others(tmp_path):
    cache = AnswerCache(tmp_path / "answers.json")
    cache.put("file:a.py", cached("old"))
    cache.put("file:b.py", cached("other"))
    cache.put("file:a.py", cached("new"))
    assert cache.get("file:a.py").text == "new" and cache.get("file:b.py").text == "other"


def test_a_cache_without_a_file_path_remembers_nothing_and_does_not_fail():
    cache = AnswerCache(None)
    cache.put("file:a.py", cached())
    assert cache.get("file:a.py") is None


@pytest.mark.parametrize("content", ["{not json", "[]", '{"answers": []}', '{"version": 99, "answers": {}}', "", '{"answers": {"file:a.py": 5}}',
                                     '{"version": 1, "answers": {"file:a.py": {"content_hash": 1, "model": "m", "when": 0, "text": "t"}}}'])
def test_an_unreadable_cache_is_ignored_and_replaced_by_the_next_answer(tmp_path, content):
    path = tmp_path / "answers.json"
    path.write_text(content)
    cache = AnswerCache(path)
    assert cache.get("file:a.py") is None
    cache.put("file:a.py", cached())
    assert cache.get("file:a.py") == cached()


def test_the_oldest_answers_go_when_there_are_too_many(tmp_path):
    cache = AnswerCache(tmp_path / "answers.json")
    for number in range(MAX_ANSWERS + 5):
        cache.put(f"file:{number}", cached(when=float(number)))
    assert cache.get("file:0") is None and cache.get("file:4") is None
    assert cache.get("file:5") is not None and cache.get(f"file:{MAX_ANSWERS + 4}") is not None
    assert len(json.loads((tmp_path / "answers.json").read_text())["answers"]) == MAX_ANSWERS


def test_a_cache_that_cannot_be_written_does_not_fail(tmp_path):
    (tmp_path / "blocked").write_text("a file where a directory should be")
    cache = AnswerCache(tmp_path / "blocked" / "answers.json")
    cache.put("file:a.py", cached())
    assert cache.get("file:a.py") is None
