"""発話分類器のテスト"""
import pytest
from orchestration.utterance_classifier import (
    UtteranceClassifier,
    UtteranceCategory,
    ClassificationResult,
    MultiClassificationResult,
)


@pytest.fixture
def classifier():
    return UtteranceClassifier()


class TestRuleBasedClassification:
    """ルールベース分類のテスト"""

    def test_profile_name(self, classifier):
        """名前の分類"""
        result = classifier._classify_with_rules("私の名前は太郎です")
        assert result.primary.category == UtteranceCategory.PROFILE
        assert "name" in result.primary.extracted_info
        assert result.primary.confidence >= 0.5

    def test_profile_age(self, classifier):
        """年齢の分類"""
        result = classifier._classify_with_rules("25歳です")
        assert result.primary.category == UtteranceCategory.PROFILE
        assert "age" in result.primary.extracted_info

    def test_preference_like(self, classifier):
        """好きなものの分類"""
        result = classifier._classify_with_rules("ラーメンが好きです")
        assert result.primary.category == UtteranceCategory.PREFERENCE
        assert "like" in result.primary.extracted_info

    def test_preference_dislike(self, classifier):
        """嫌いなものの分類"""
        result = classifier._classify_with_rules("虫が嫌いです")
        assert result.primary.category == UtteranceCategory.PREFERENCE
        assert "dislike" in result.primary.extracted_info

    def test_promise_future(self, classifier):
        """約束の分類"""
        result = classifier._classify_with_rules("今度映画を見に行こう")
        assert result.primary.category == UtteranceCategory.PROMISE
        assert result.primary.confidence >= 0.5

    def test_boundary_ng(self, classifier):
        """NGの分類"""
        result = classifier._classify_with_rules("急に電話しないで")
        assert result.primary.category == UtteranceCategory.BOUNDARY
        assert "ng_action" in result.primary.extracted_info

    def test_chit_chat_greeting(self, classifier):
        """挨拶の分類"""
        result = classifier._classify_with_rules("おはよう")
        assert result.primary.category == UtteranceCategory.CHIT_CHAT
        assert result.primary.extracted_info.get("type") == "greeting"

    def test_chit_chat_farewell(self, classifier):
        """別れの挨拶の分類"""
        result = classifier._classify_with_rules("じゃあね")
        assert result.primary.category == UtteranceCategory.CHIT_CHAT
        assert result.primary.extracted_info.get("type") == "farewell"

    def test_default_chit_chat(self, classifier):
        """パターンにマッチしない場合のデフォルト"""
        result = classifier._classify_with_rules("あのさー")
        assert result.primary.category == UtteranceCategory.CHIT_CHAT
        assert result.primary.confidence == 0.5


class TestClassificationResult:
    """分類結果のテスト"""

    def test_to_dict(self):
        """to_dictメソッド"""
        result = ClassificationResult(
            category=UtteranceCategory.PROFILE,
            confidence=0.8,
            extracted_info={"name": "太郎"},
            reasoning="名前のパターンマッチ"
        )
        d = result.to_dict()
        assert d["category"] == "profile"
        assert d["confidence"] == 0.8
        assert d["extracted_info"]["name"] == "太郎"

    def test_multi_classification_all_results(self):
        """複数分類結果のall_results"""
        primary = ClassificationResult(
            category=UtteranceCategory.PROFILE,
            confidence=0.8,
            extracted_info={}
        )
        secondary = ClassificationResult(
            category=UtteranceCategory.PREFERENCE,
            confidence=0.5,
            extracted_info={}
        )
        multi = MultiClassificationResult(primary=primary, secondary=[secondary])

        assert len(multi.all_results) == 2
        assert multi.all_results[0].category == UtteranceCategory.PROFILE
        assert multi.all_results[1].category == UtteranceCategory.PREFERENCE


class TestClassifyMethod:
    """classifyメソッドのテスト"""

    def test_classify_without_llm(self, classifier):
        """LLMなしでの分類"""
        result = classifier.classify("私の名前は花子です", use_llm=False)
        assert isinstance(result, MultiClassificationResult)
        assert result.primary.category == UtteranceCategory.PROFILE

    def test_classify_with_context(self, classifier):
        """コンテキスト付きの分類"""
        context = [
            {"role": "assistant", "content": "お名前を教えてください"},
        ]
        result = classifier.classify("太郎です", context=context, use_llm=False)
        assert isinstance(result, MultiClassificationResult)


class TestEdgeCases:
    """エッジケースのテスト"""

    def test_empty_string(self, classifier):
        """空文字列"""
        result = classifier._classify_with_rules("")
        assert result.primary.category == UtteranceCategory.CHIT_CHAT

    def test_long_text(self, classifier):
        """長いテキスト"""
        long_text = "今日は天気がいいですね。" * 100
        result = classifier._classify_with_rules(long_text)
        assert result.primary.category == UtteranceCategory.CHIT_CHAT

    def test_mixed_content(self, classifier):
        """複合的な内容"""
        # 名前と好みが両方含まれる場合
        result = classifier._classify_with_rules("私の名前は太郎で、ラーメンが好きです")
        # 最初にマッチしたものがprimaryになる
        assert result.primary.category in [UtteranceCategory.PROFILE, UtteranceCategory.PREFERENCE]
