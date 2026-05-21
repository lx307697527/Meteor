"""Unit tests for voiceime.context.rules — ContextRuleRepo CRUD."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def rules_file(tmp_path):
    """Temporary context_rules.json path."""
    return tmp_path / "context_rules.json"


class TestContextRuleRepoLoad:
    def test_should_load_default_rules_when_file_missing(self, rules_file):
        from voiceime.context.rules import ContextRuleRepo

        repo = ContextRuleRepo(rules_file)
        rules = repo.list_all()
        assert len(rules) >= 3
        names = {r["name"] for r in rules}
        assert "VSCode 代码注释" in names
        assert "微信快速上屏" in names

    def test_should_load_from_existing_file(self, rules_file):
        custom = [{"name": "test", "app_name_pattern": "test.exe", "title_pattern": "", "enabled": True, "overrides": {}}]
        rules_file.write_text(json.dumps(custom), encoding="utf-8")

        from voiceime.context.rules import ContextRuleRepo

        repo = ContextRuleRepo(rules_file)
        rules = repo.list_all()
        assert len(rules) == 1
        assert rules[0]["name"] == "test"

    def test_should_recover_from_corrupted_file(self, rules_file):
        rules_file.write_text("not valid json {{{", encoding="utf-8")

        from voiceime.context.rules import ContextRuleRepo

        repo = ContextRuleRepo(rules_file)
        rules = repo.list_all()
        assert len(rules) >= 3  # defaults loaded
        assert rules_file.with_suffix(".json.bak").exists()

    def test_should_recover_from_wrong_type(self, rules_file):
        rules_file.write_text('{"not": "a list"}', encoding="utf-8")

        from voiceime.context.rules import ContextRuleRepo

        repo = ContextRuleRepo(rules_file)
        rules = repo.list_all()
        assert len(rules) >= 3  # defaults loaded


class TestContextRuleRepoCRUD:
    @pytest.fixture
    def repo(self, rules_file):
        from voiceime.context.rules import ContextRuleRepo
        return ContextRuleRepo(rules_file)

    def test_should_add_rule_and_persist(self, repo):
        rule = {"name": "Test", "app_name_pattern": "test.exe", "title_pattern": "", "enabled": True, "overrides": {}}
        repo.add(rule)
        rules = repo.list_all()
        assert len(rules) >= 1
        assert rules[-1]["name"] == "Test"

    def test_should_update_rule_by_index(self, repo):
        rule = {"name": "Updated", "app_name_pattern": "u.exe", "title_pattern": "x", "enabled": False, "overrides": {"quick_mode": True}}
        repo.update(0, rule)
        rules = repo.list_all()
        assert rules[0]["name"] == "Updated"
        assert rules[0]["overrides"]["quick_mode"] is True

    def test_should_raise_on_update_out_of_range(self, repo):
        with pytest.raises(IndexError):
            repo.update(999, {})

    def test_should_delete_rule_by_index(self, repo):
        initial_count = len(repo.list_all())
        result = repo.delete(0)
        assert result is True
        assert len(repo.list_all()) == initial_count - 1

    def test_should_return_false_on_delete_out_of_range(self, repo):
        result = repo.delete(999)
        assert result is False

    def test_should_set_all_rules(self, repo):
        new_rules = [{"name": "only", "app_name_pattern": "x.exe", "title_pattern": "", "enabled": True, "overrides": {}}]
        repo.set_all(new_rules)
        assert len(repo.list_all()) == 1
        assert repo.list_all()[0]["name"] == "only"

    def test_should_raise_when_max_rules_reached(self, rules_file):
        from voiceime.context.rules import ContextRuleRepo

        repo = ContextRuleRepo(rules_file)
        repo.set_all([])
        for i in range(200):
            repo.add({"name": f"r{i}", "app_name_pattern": f"a{i}.exe", "title_pattern": "", "enabled": True, "overrides": {}})
        with pytest.raises(ValueError, match="Max rules"):
            repo.add({"name": "overflow", "app_name_pattern": "o.exe", "title_pattern": "", "enabled": True, "overrides": {}})
