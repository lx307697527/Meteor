"""Tests for HistoryRepo — SQLite CRUD, search, app filter, integrity check."""

from __future__ import annotations

from pathlib import Path

import pytest

from voiceime.history.repository import HistoryRepo
from voiceime.protocols import HistoryRecord


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_history.sqlite"


@pytest.fixture
def repo(db_path):
    r = HistoryRepo(db_path=db_path)
    yield r
    r.close()


def _make_record(**kwargs) -> HistoryRecord:
    defaults = {
        "text": "你好世界",
        "raw_text": "你好世界",
        "language": "zh",
        "app_name": "notepad.exe",
        "app_title": "Untitled",
        "audio_duration_ms": 3000,
        "inference_time_ms": 1200,
        "is_polished": False,
    }
    defaults.update(kwargs)
    return HistoryRecord(**defaults)


class TestHistoryRepoCRUD:
    def test_should_save_and_retrieve_record(self, repo):
        record = _make_record()
        rid = repo.save(record)
        assert rid > 0
        loaded = repo.get_by_id(rid)
        assert loaded is not None
        assert loaded.text == "你好世界"
        assert loaded.language == "zh"

    def test_should_return_none_for_nonexistent_id(self, repo):
        assert repo.get_by_id(99999) is None

    def test_should_delete_record(self, repo):
        rid = repo.save(_make_record())
        assert repo.delete(rid) is True
        assert repo.get_by_id(rid) is None

    def test_should_return_false_deleting_nonexistent(self, repo):
        assert repo.delete(99999) is False

    def test_should_clear_all_records(self, repo):
        repo.save(_make_record())
        repo.save(_make_record(text="第二条"))
        count = repo.clear_all()
        assert count == 2
        assert repo.total_count == 0

    def test_should_track_total_count(self, repo):
        assert repo.total_count == 0
        repo.save(_make_record())
        assert repo.total_count == 1
        repo.save(_make_record())
        assert repo.total_count == 2

    def test_should_auto_generate_created_at(self, repo):
        rid = repo.save(_make_record(created_at=""))
        loaded = repo.get_by_id(rid)
        assert loaded is not None
        assert loaded.created_at != ""


class TestHistoryRepoSearch:
    def test_should_search_by_text(self, repo):
        repo.save(_make_record(text="语音输入法"))
        repo.save(_make_record(text="文本处理"))
        results = repo.search("语音")
        assert len(results) == 1
        assert results[0].text == "语音输入法"

    def test_should_filter_by_app_name(self, repo):
        repo.save(_make_record(app_name="Code.exe"))
        repo.save(_make_record(app_name="notepad.exe"))
        results = repo.search(app_filter="Code.exe")
        assert len(results) == 1
        assert results[0].app_name == "Code.exe"

    def test_should_combine_text_and_app_filter(self, repo):
        repo.save(_make_record(text="代码注释", app_name="Code.exe"))
        repo.save(_make_record(text="代码注释", app_name="notepad.exe"))
        repo.save(_make_record(text="其他文本", app_name="Code.exe"))
        results = repo.search(query="代码", app_filter="Code.exe")
        assert len(results) == 1
        assert results[0].text == "代码注释"

    def test_should_return_all_when_no_filters(self, repo):
        repo.save(_make_record())
        repo.save(_make_record())
        results = repo.search()
        assert len(results) == 2

    def test_should_respect_limit_and_offset(self, repo):
        for i in range(5):
            repo.save(_make_record(text=f"记录{i}"))
        results = repo.search(limit=2, offset=0)
        assert len(results) == 2
        results2 = repo.search(limit=2, offset=2)
        assert len(results2) == 2
        # Ensure different records
        assert results[0].id != results2[0].id

    def test_should_order_by_created_at_desc(self, repo):
        repo.save(_make_record(text="first"))
        repo.save(_make_record(text="second"))
        results = repo.search()
        assert results[0].text == "second"
        assert results[1].text == "first"


class TestHistoryRepoIntegrity:
    def test_should_pass_integrity_check(self, repo):
        assert repo.check_integrity() is True

    def test_should_rebuild_on_corruption(self, db_path):
        repo = HistoryRepo(db_path=db_path)
        repo.save(_make_record())
        repo.close()
        # Corrupt the database
        db_path.write_bytes(b"corrupted data here")
        repo2 = HistoryRepo(db_path=db_path)
        assert repo2.total_count == 0
        assert db_path.with_suffix(".sqlite.bak").exists()
        repo2.close()
