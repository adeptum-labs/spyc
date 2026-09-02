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


import logging
from pathlib import Path

from spyc.state import MAX_RECENT, StateStore, configure_logging, default_state_path


def test_values_survive_a_new_store(tmp_path):
    StateStore(tmp_path / "state.json").set("sidebar", 40)
    assert StateStore(tmp_path / "state.json").get("sidebar") == 40


def test_missing_keys_give_the_default(tmp_path):
    assert StateStore(tmp_path / "state.json").get("nothing", "fallback") == "fallback"


def test_a_corrupt_file_is_ignored(tmp_path):
    (tmp_path / "state.json").write_text("{not json")
    assert StateStore(tmp_path / "state.json").get("sidebar", 1) == 1


def test_a_file_holding_something_else_than_an_object_is_ignored(tmp_path):
    (tmp_path / "state.json").write_text("[1, 2]")
    assert StateStore(tmp_path / "state.json").get("sidebar", 1) == 1


def test_recent_files_are_newest_first_without_duplicates(tmp_path):
    store = StateStore(tmp_path / "state.json")
    for name in ("a.py", "b.py", "a.py"):
        store.add_recent_file(Path("/project"), name)
    assert store.recent_files(Path("/project")) == ["a.py", "b.py"]
    assert store.recent_files(Path("/other")) == []


def test_recent_files_are_capped(tmp_path):
    store = StateStore(tmp_path / "state.json")
    for number in range(MAX_RECENT + 5):
        store.add_recent_file(Path("/project"), f"f{number}.py")
    recent = store.recent_files(Path("/project"))
    assert len(recent) == MAX_RECENT and recent[0] == f"f{MAX_RECENT + 4}.py"


def test_an_unwritable_location_never_raises(tmp_path):
    (tmp_path / "blocker").write_text("a file, not a directory")
    store = StateStore(tmp_path / "blocker" / "state.json")
    store.set("sidebar", 40)
    assert store.get("sidebar") == 40


def test_the_default_path_follows_xdg_state_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert default_state_path() == tmp_path / "spyc" / "state.json"


def test_warnings_are_written_to_the_log_file(tmp_path):
    handler = configure_logging(tmp_path / "spyc.log")
    try:
        logging.getLogger("spyc.something").warning("boom")
        handler.flush()
        assert "boom" in (tmp_path / "spyc.log").read_text()
        assert configure_logging(tmp_path / "spyc.log") is handler
    finally:
        logging.getLogger().removeHandler(handler)
        handler.close()


def test_an_unwritable_log_location_is_not_fatal(tmp_path):
    (tmp_path / "blocker").write_text("a file")
    assert configure_logging(tmp_path / "blocker" / "spyc.log") is None
