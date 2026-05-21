"""Tests for HotwordRepo — JSON CRUD, case-insensitive find, CSV import/export."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from voiceime.hotword.repository import HotwordRepo


@pytest.fixture
def hotword_file(tmp_path):
    return tmp_path / "hotwords.json"


@pytest.fixture
def repo(hotword_file):
    return HotwordRepo(path=hotword_file)


class TestHotwordRepoCRUD:
    def test_should_add_entry_when_add_called(self, repo, hotword_file):
        repo.add("你尼达", "UniData")
        data = json.loads(hotword_file.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["trigger"] == "你尼达"
        assert data[0]["replace"] == "UniData"

    def test_should_find_case_insensitive_by_default(self, repo):
        repo.add("Hello", "World")
        assert repo.find("hello") == "World"
        assert repo.find("HELLO") == "World"

    def test_should_find_case_sensitive_when_enabled(self, repo):
        repo.add("Hello", "World", case_sensitive=True)
        assert repo.find("Hello") == "World"
        assert repo.find("hello") is None

    def test_should_return_none_when_trigger_not_found(self, repo):
        assert repo.find("nonexistent") is None

    def test_should_update_entry_when_update_called(self, repo, hotword_file):
        repo.add("old", "OldValue")
        repo.update(0, "new", "NewValue")
        assert repo.find("new") == "NewValue"
        assert repo.find("old") is None

    def test_should_raise_when_update_index_out_of_range(self, repo):
        with pytest.raises(IndexError):
            repo.update(99, "x", "y")

    def test_should_delete_entry_when_delete_called(self, repo, hotword_file):
        repo.add("del_me", "value")
        assert repo.delete(0) is True
        assert repo.find("del_me") is None
        assert len(repo.list_all()) == 0

    def test_should_return_false_when_delete_index_out_of_range(self, repo):
        assert repo.delete(99) is False

    def test_should_list_all_entries(self, repo):
        repo.add("a", "A")
        repo.add("b", "B")
        entries = repo.list_all()
        assert len(entries) == 2
        assert entries[0]["trigger"] == "a"
        assert entries[1]["trigger"] == "b"


class TestHotwordRepoPersistence:
    def test_should_persist_to_json_on_add(self, repo, hotword_file):
        repo.add("test", "value")
        raw = hotword_file.read_text(encoding="utf-8")
        assert "test" in raw

    def test_should_load_existing_json_on_init(self, hotword_file):
        hotword_file.write_text(
            json.dumps([{"trigger": "hello", "replace": "world", "case_sensitive": False}],
                       ensure_ascii=False),
            encoding="utf-8",
        )
        repo = HotwordRepo(path=hotword_file)
        assert repo.find("hello") == "world"

    def test_should_reset_on_corrupted_json(self, hotword_file):
        hotword_file.write_text("{invalid json}", encoding="utf-8")
        repo = HotwordRepo(path=hotword_file)
        assert repo.list_all() == []
        assert hotword_file.with_suffix(".json.bak").exists()

    def test_should_handle_empty_file(self, hotword_file):
        hotword_file.write_text("", encoding="utf-8")
        repo = HotwordRepo(path=hotword_file)
        assert repo.list_all() == []


class TestHotwordRepoCSV:
    def test_should_import_csv(self, repo, tmp_path):
        csv_file = tmp_path / "hotwords.csv"
        csv_file.write_text("你尼达,UniData\nhello,world\n", encoding="utf-8-sig")
        count = repo.import_csv(csv_file)
        assert count == 2
        assert repo.find("你尼达") == "UniData"
        assert repo.find("hello") == "world"

    def test_should_deduplicate_on_import(self, repo, tmp_path):
        repo.add("hello", "World")
        csv_file = tmp_path / "hotwords.csv"
        csv_file.write_text("hello,duplicate\nnew,entry\n", encoding="utf-8-sig")
        count = repo.import_csv(csv_file)
        assert count == 1
        assert repo.find("new") == "entry"
        # Original value preserved
        assert repo.find("hello") == "World"

    def test_should_skip_invalid_rows(self, repo, tmp_path):
        csv_file = tmp_path / "hotwords.csv"
        csv_file.write_text(",empty_trigger\ntrigger_only,\nvalid,replacement\n",
                            encoding="utf-8-sig")
        count = repo.import_csv(csv_file)
        assert count == 1
        assert repo.find("valid") == "replacement"

    def test_should_export_csv(self, repo, tmp_path):
        repo.add("你尼达", "UniData")
        repo.add("hello", "world")
        csv_file = tmp_path / "export.csv"
        repo.export_csv(csv_file)
        content = csv_file.read_text(encoding="utf-8-sig")
        assert "trigger" in content  # header
        assert "你尼达" in content
        assert "hello" in content
