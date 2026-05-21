"""Tests for punctuation normalization."""

from voiceime.postprocess.punct import normalize_punctuation, remove_trailing_particles


class TestNormalizePunctuation:
    def test_should_convert_comma_in_cjk_context(self):
        assert normalize_punctuation("你好,世界") == "你好，世界"

    def test_should_convert_period_in_cjk_context(self):
        assert normalize_punctuation("你好.世界") == "你好。世界"

    def test_should_convert_question_mark_in_cjk_context(self):
        assert normalize_punctuation("你好吗?") == "你好吗？"

    def test_should_convert_exclamation_in_cjk_context(self):
        assert normalize_punctuation("好!") == "好！"

    def test_should_convert_colon_in_cjk_context(self):
        assert normalize_punctuation("备注:这是测试") == "备注：这是测试"

    def test_should_convert_semicolon_in_cjk_context(self):
        assert normalize_punctuation("第一;第二") == "第一；第二"

    def test_should_not_convert_english_punctuation_in_english(self):
        assert normalize_punctuation("Hello, world.") == "Hello, world."

    def test_should_convert_trailing_period_after_cjk(self):
        assert normalize_punctuation("测试结束.") == "测试结束。"

    def test_should_handle_empty_string(self):
        assert normalize_punctuation("") == ""


class TestRemoveTrailingParticles:
    def test_should_remove_trailing_a(self):
        assert remove_trailing_particles("你好啊") == "你好"

    def test_should_remove_trailing_ne(self):
        assert remove_trailing_particles("是吗呢") == "是吗"

    def test_should_remove_trailing_ba(self):
        assert remove_trailing_particles("走吧") == "走"

    def test_should_not_remove_mid_sentence_particles(self):
        # "好啊走吧" — particles are not at end of sentence, regex only matches at $
        assert remove_trailing_particles("好啊走吧") == "好啊走"

    def test_should_handle_empty_string(self):
        assert remove_trailing_particles("") == ""

    def test_should_preserve_text_without_particles(self):
        assert remove_trailing_particles("正常文本") == "正常文本"
