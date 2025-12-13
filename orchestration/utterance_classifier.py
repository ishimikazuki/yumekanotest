"""UtteranceClassifier: ユーザー発話の分類

発話を以下のカテゴリに分類し、confidence スコアを付与する:
- profile: ユーザーの自己情報（名前、年齢、職業、住所など）
- preference: 好み・嗜好（好きなもの、嫌いなもの）
- promise: 約束・予定（「今度〇〇しよう」「明日〇〇する」）
- boundary: NG・境界線（「〇〇しないで」「〇〇は嫌」）
- chit-chat: 雑談・挨拶・一般会話
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Literal
from enum import Enum


class UtteranceCategory(str, Enum):
    """発話カテゴリ"""
    PROFILE = "profile"
    PREFERENCE = "preference"
    PROMISE = "promise"
    BOUNDARY = "boundary"
    CHIT_CHAT = "chit-chat"


@dataclass
class ClassificationResult:
    """分類結果"""
    category: UtteranceCategory
    confidence: float  # 0.0 - 1.0
    extracted_info: Dict = field(default_factory=dict)
    reasoning: str = ""

    def to_dict(self) -> Dict:
        return {
            "category": self.category.value,
            "confidence": self.confidence,
            "extracted_info": self.extracted_info,
            "reasoning": self.reasoning
        }


@dataclass
class MultiClassificationResult:
    """複数分類結果（1発話が複数カテゴリに該当する場合）"""
    primary: ClassificationResult
    secondary: List[ClassificationResult] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "primary": self.primary.to_dict(),
            "secondary": [s.to_dict() for s in self.secondary]
        }

    @property
    def all_results(self) -> List[ClassificationResult]:
        return [self.primary] + self.secondary


# ルールベース分類用のパターン
PROFILE_PATTERNS = [
    (r"(?:私|俺|僕|わたし|おれ|ぼく)(?:の名前)?は(.+?)(?:です|だよ|だ|っていう)", "name"),
    (r"(.+?)(?:歳|才)(?:です|だよ|だ|。|$)", "age"),
    (r"(?:仕事|職業)は(.+?)(?:です|だよ|だ|をして)", "occupation"),
    (r"(?:住んでる|住んでいる|住まい)(?:のは|場所は)?(.+?)(?:です|だよ|だ|。|$)", "location"),
    (r"誕生日は(.+?)(?:です|だよ|だ|。|$)", "birthday"),
]

PREFERENCE_PATTERNS = [
    (r"(.+?)(?:が|は)(?:好き|大好き|すき)", "like"),
    (r"(.+?)(?:が|は)(?:嫌い|きらい|苦手)", "dislike"),
    (r"(?:好きな|お気に入りの)(.+?)は(.+?)(?:です|だよ|だ|。|$)", "favorite"),
    (r"(?:趣味|ハマってる|ハマっている)(?:は|が)(.+?)(?:です|だよ|だ|。|$)", "hobby"),
]

PROMISE_PATTERNS = [
    (r"(?:今度|いつか|次|明日|来週)(.+?)(?:しよう|しようね|する|行こう|行く)", "future_plan"),
    (r"約束(?:する|だよ|ね)", "explicit_promise"),
    (r"(?:必ず|絶対)(.+?)(?:する|行く|会う)", "commitment"),
]

BOUNDARY_PATTERNS = [
    (r"(.+?)(?:しないで|やめて|はNG|は嫌|はダメ)", "ng_action"),
    (r"(.+?)(?:の話|について)(?:は|しないで|やめて)", "ng_topic"),
    (r"(?:触れないで|聞かないで)(.+?)", "sensitive_topic"),
]

CHIT_CHAT_PATTERNS = [
    (r"^(?:おはよう|こんにちは|こんばんは|やあ|ハロー|はーい)", "greeting"),
    (r"^(?:お疲れ|おつかれ|元気|調子どう)", "casual_greeting"),
    (r"(?:天気|暑い|寒い|雨)", "weather"),
    (r"^(?:ありがとう|サンキュー|感謝)", "thanks"),
    (r"^(?:じゃあね|バイバイ|またね|おやすみ)", "farewell"),
]


class UtteranceClassifier:
    """
    ユーザー発話分類器

    LLMベースの分類を優先し、フォールバックとしてルールベースを使用。
    """

    def __init__(self):
        self._llm_client = None

    @property
    def llm_client(self):
        """遅延初期化でLLMクライアントを取得"""
        if self._llm_client is None:
            from .llm_client import llm_client
            self._llm_client = llm_client
        return self._llm_client

    def classify(
        self,
        utterance: str,
        context: Optional[List[Dict]] = None,
        use_llm: bool = True
    ) -> MultiClassificationResult:
        """
        発話を分類する。

        Args:
            utterance: ユーザー発話
            context: 会話履歴（オプション）
            use_llm: LLMを使用するか

        Returns:
            MultiClassificationResult: 分類結果
        """
        if use_llm:
            try:
                return self._classify_with_llm(utterance, context)
            except Exception as e:
                print(f"[UtteranceClassifier] LLM分類エラー: {e}")

        # フォールバック: ルールベース
        return self._classify_with_rules(utterance)

    def _classify_with_llm(
        self,
        utterance: str,
        context: Optional[List[Dict]] = None
    ) -> MultiClassificationResult:
        """LLMを使用した分類"""
        context_text = ""
        if context:
            recent = context[-3:]
            context_text = "\n".join([
                f"{m['role']}: {m['content']}" for m in recent
            ])

        prompt = f"""ユーザーの発話を分析し、以下のカテゴリに分類してください。

## カテゴリ定義
- profile: ユーザー自身の情報（名前、年齢、職業、住所、誕生日など）
- preference: 好み・嗜好（好きなもの、嫌いなもの、趣味）
- promise: 約束・将来の予定（「今度〇〇しよう」「明日〇〇する」）
- boundary: NG・境界線（「〇〇しないで」「〇〇の話は嫌」）
- chit-chat: 雑談・挨拶・一般的な会話

## 会話履歴
{context_text if context_text else "なし"}

## ユーザー発話
{utterance}

## 出力形式（JSON）
{{
    "primary": {{
        "category": "カテゴリ名",
        "confidence": 0.0-1.0,
        "extracted_info": {{"key": "抽出した情報"}},
        "reasoning": "分類理由"
    }},
    "secondary": [
        // 他に該当するカテゴリがあれば（なければ空配列）
    ]
}}

## 注意
- 1つの発話が複数カテゴリに該当する場合は secondary に追加
- confidence は分類の確信度（0.8以上で高確信）
- extracted_info には具体的に抽出した情報を入れる
  - profile: {{"name": "太郎"}}, {{"age": 25}} など
  - preference: {{"like": "ラーメン"}}, {{"hobby": "ゲーム"}} など
  - promise: {{"plan": "来週映画を見に行く"}} など
  - boundary: {{"ng_topic": "元カノの話"}}, {{"ng_action": "急に電話する"}} など
"""

        schema = {
            "type": "object",
            "properties": {
                "primary": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "enum": ["profile", "preference", "promise", "boundary", "chit-chat"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "extracted_info": {"type": "object"},
                        "reasoning": {"type": "string"}
                    },
                    "required": ["category", "confidence"]
                },
                "secondary": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string"},
                            "confidence": {"type": "number"},
                            "extracted_info": {"type": "object"},
                            "reasoning": {"type": "string"}
                        }
                    }
                }
            },
            "required": ["primary"]
        }

        result = self.llm_client.json_chat(
            messages=[{"role": "user", "content": prompt}],
            schema=schema,
            system_prompt="あなたは発話分析の専門家です。ユーザーの発話を正確に分類してください。"
        )

        primary_data = result.get("primary", {})
        primary = ClassificationResult(
            category=UtteranceCategory(primary_data.get("category", "chit-chat")),
            confidence=float(primary_data.get("confidence", 0.5)),
            extracted_info=primary_data.get("extracted_info", {}),
            reasoning=primary_data.get("reasoning", "")
        )

        secondary = []
        for sec_data in result.get("secondary", []):
            try:
                secondary.append(ClassificationResult(
                    category=UtteranceCategory(sec_data.get("category", "chit-chat")),
                    confidence=float(sec_data.get("confidence", 0.3)),
                    extracted_info=sec_data.get("extracted_info", {}),
                    reasoning=sec_data.get("reasoning", "")
                ))
            except ValueError:
                pass  # 無効なカテゴリはスキップ

        return MultiClassificationResult(primary=primary, secondary=secondary)

    def _classify_with_rules(self, utterance: str) -> MultiClassificationResult:
        """ルールベースの分類（フォールバック）"""
        results: List[ClassificationResult] = []

        # Profile チェック
        for pattern, info_key in PROFILE_PATTERNS:
            match = re.search(pattern, utterance)
            if match:
                extracted = match.group(1) if match.groups() else ""
                results.append(ClassificationResult(
                    category=UtteranceCategory.PROFILE,
                    confidence=0.7,
                    extracted_info={info_key: extracted.strip()},
                    reasoning=f"パターンマッチ: {info_key}"
                ))
                break

        # Preference チェック
        for pattern, info_key in PREFERENCE_PATTERNS:
            match = re.search(pattern, utterance)
            if match:
                extracted = match.group(1) if match.groups() else ""
                results.append(ClassificationResult(
                    category=UtteranceCategory.PREFERENCE,
                    confidence=0.7,
                    extracted_info={info_key: extracted.strip()},
                    reasoning=f"パターンマッチ: {info_key}"
                ))
                break

        # Promise チェック
        for pattern, info_key in PROMISE_PATTERNS:
            match = re.search(pattern, utterance)
            if match:
                extracted = match.group(1) if match.groups() else utterance
                results.append(ClassificationResult(
                    category=UtteranceCategory.PROMISE,
                    confidence=0.6,
                    extracted_info={info_key: extracted.strip()},
                    reasoning=f"パターンマッチ: {info_key}"
                ))
                break

        # Boundary チェック
        for pattern, info_key in BOUNDARY_PATTERNS:
            match = re.search(pattern, utterance)
            if match:
                extracted = match.group(1) if match.groups() else utterance
                results.append(ClassificationResult(
                    category=UtteranceCategory.BOUNDARY,
                    confidence=0.7,
                    extracted_info={info_key: extracted.strip()},
                    reasoning=f"パターンマッチ: {info_key}"
                ))
                break

        # Chit-chat チェック
        for pattern, info_key in CHIT_CHAT_PATTERNS:
            match = re.search(pattern, utterance)
            if match:
                results.append(ClassificationResult(
                    category=UtteranceCategory.CHIT_CHAT,
                    confidence=0.8,
                    extracted_info={"type": info_key},
                    reasoning=f"パターンマッチ: {info_key}"
                ))
                break

        # 結果がなければデフォルトでchit-chat
        if not results:
            results.append(ClassificationResult(
                category=UtteranceCategory.CHIT_CHAT,
                confidence=0.5,
                extracted_info={},
                reasoning="デフォルト分類"
            ))

        # 最もconfidenceが高いものをprimaryに
        results.sort(key=lambda r: r.confidence, reverse=True)
        primary = results[0]
        secondary = results[1:] if len(results) > 1 else []

        return MultiClassificationResult(primary=primary, secondary=secondary)


# シングルトンインスタンス
utterance_classifier = UtteranceClassifier()
