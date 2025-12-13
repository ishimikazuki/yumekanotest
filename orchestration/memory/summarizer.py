"""会話要約生成

短期記憶の会話を要約して中期記憶に昇格させる。
"""
from __future__ import annotations

from typing import Dict, List, Optional
import json


def summarize_conversation(messages: List[Dict], llm_client=None) -> Dict:
    """
    会話履歴を要約する。

    Args:
        messages: [{"role": "user", "content": "..."}, ...]
        llm_client: LLMクライアント（省略時は内部で取得）

    Returns:
        {
            "summary": "要約テキスト",
            "importance": 0.0-1.0,
            "key_facts": ["事実1", "事実2", ...],
            "emotional_events": ["感情的イベント1", ...]
        }
    """
    if not messages:
        return {
            "summary": "",
            "importance": 0.0,
            "key_facts": [],
            "emotional_events": []
        }

    if llm_client is None:
        from ..llm_client import LLMClient
        llm_client = LLMClient()

    # 会話をテキスト形式に変換
    conversation_text = _format_conversation(messages)

    prompt = f"""以下の会話を分析し、JSON形式で要約してください。

会話:
{conversation_text}

以下の形式で出力してください:
{{
    "summary": "会話の要約（2-3文）",
    "importance": 0.0から1.0の重要度スコア（日常会話=0.3、重要な話題=0.7、感情的に重要=0.9）,
    "key_facts": ["ユーザーについて判明した事実のリスト"],
    "emotional_events": ["感情的に重要な出来事のリスト"]
}}

注意:
- key_factsには、ユーザーの好み、経験、状況など覚えておくべき事実を含める
- emotional_eventsには、喜び、悲しみ、怒りなど感情的に重要な出来事を含める
- importanceは、この会話が今後の関係構築にどれだけ重要かを示す
"""

    try:
        result = llm_client.json_chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="あなたは会話分析の専門家です。会話から重要な情報を抽出します。"
        )

        # 結果の検証とデフォルト値の設定
        return {
            "summary": result.get("summary", ""),
            "importance": min(1.0, max(0.0, float(result.get("importance", 0.5)))),
            "key_facts": result.get("key_facts", []),
            "emotional_events": result.get("emotional_events", [])
        }
    except Exception as e:
        print(f"[Summarizer] 要約生成エラー: {e}")
        # フォールバック: 簡易要約
        return {
            "summary": _simple_summary(messages),
            "importance": 0.5,
            "key_facts": [],
            "emotional_events": []
        }


def _format_conversation(messages: List[Dict]) -> str:
    """会話をテキスト形式に変換"""
    lines = []
    for msg in messages:
        role = "ユーザー" if msg["role"] == "user" else "アシスタント"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


def _simple_summary(messages: List[Dict]) -> str:
    """簡易要約（LLMが失敗した場合のフォールバック）"""
    user_messages = [m["content"] for m in messages if m["role"] == "user"]
    if not user_messages:
        return "会話なし"

    # 最初と最後のユーザーメッセージを使った簡易要約
    if len(user_messages) == 1:
        return f"ユーザーが「{user_messages[0][:50]}...」について話した"

    return f"ユーザーが「{user_messages[0][:30]}...」から「{user_messages[-1][:30]}...」まで{len(user_messages)}回発言した会話"


def extract_long_term_memories(summary_result: Dict) -> List[Dict]:
    """
    要約結果から長期記憶に保存すべき項目を抽出する。

    Args:
        summary_result: summarize_conversationの結果

    Returns:
        [{"content": "...", "memory_type": "fact|emotion|preference|event", "importance": 0.0-1.0}, ...]
    """
    memories = []

    # 重要な事実を抽出
    for fact in summary_result.get("key_facts", []):
        if fact:
            memories.append({
                "content": fact,
                "memory_type": "fact",
                "importance": summary_result.get("importance", 0.5)
            })

    # 感情的イベントを抽出
    for event in summary_result.get("emotional_events", []):
        if event:
            memories.append({
                "content": event,
                "memory_type": "emotion",
                "importance": min(1.0, summary_result.get("importance", 0.5) + 0.2)
            })

    return memories
