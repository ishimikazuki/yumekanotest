"""構造化メモリ管理

ユーザープロフィール、約束、境界線（NG）を構造化して管理する。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any

from .supabase_client import get_supabase


# 分類の最小confidence閾値
MIN_CONFIDENCE_THRESHOLD = 0.6


@dataclass
class UserProfile:
    """ユーザープロフィール"""
    user_id: str
    name: Optional[str] = None
    age: Optional[int] = None
    occupation: Optional[str] = None
    location: Optional[str] = None
    birthday: Optional[str] = None
    hobbies: List[str] = field(default_factory=list)
    preferences: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "age": self.age,
            "occupation": self.occupation,
            "location": self.location,
            "birthday": self.birthday,
            "hobbies": self.hobbies,
            "preferences": self.preferences,
        }


@dataclass
class Promise:
    """約束"""
    id: str
    user_id: str
    content: str
    created_at: str
    due_date: Optional[str] = None
    status: str = "pending"  # pending, fulfilled, broken

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content": self.content,
            "created_at": self.created_at,
            "due_date": self.due_date,
            "status": self.status,
        }


@dataclass
class Boundary:
    """境界線（NG）"""
    id: str
    user_id: str
    content: str
    category: str  # topic, action, time
    severity: float  # 0.0-1.0
    created_at: str

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content": self.content,
            "category": self.category,
            "severity": self.severity,
            "created_at": self.created_at,
        }


class StructuredMemoryManager:
    """
    構造化メモリマネージャー

    プロフィール、約束、境界線を管理する。
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._supabase = get_supabase()

    # ==================== Profile ====================

    def save_profile(self, field_name: str, value: Any) -> bool:
        """
        プロフィールのフィールドを保存する。

        Args:
            field_name: フィールド名（name, age, occupation, location, birthday, hobby, preference）
            value: 値

        Returns:
            成功したかどうか
        """
        try:
            # 現在のプロフィールを取得
            current = self._get_raw_profile()

            # フィールドに応じて更新
            if field_name == "hobby":
                # 趣味は配列に追加
                hobbies = current.get("hobbies", []) or []
                if value not in hobbies:
                    hobbies.append(value)
                current["hobbies"] = hobbies
            elif field_name.startswith("preference_"):
                # preference_food -> preferences["food"]
                pref_key = field_name.replace("preference_", "")
                preferences = current.get("preferences", {}) or {}
                preferences[pref_key] = value
                current["preferences"] = preferences
            else:
                # その他は直接更新
                current[field_name] = value

            # user_idを設定
            current["user_id"] = self.user_id

            # upsert
            self._supabase.table("user_profiles").upsert(current).execute()
            return True

        except Exception as e:
            print(f"[StructuredMemory] プロフィール保存エラー: {e}")
            return False

    def get_profile(self) -> UserProfile:
        """
        プロフィールを取得する。

        Returns:
            UserProfile
        """
        data = self._get_raw_profile()
        return UserProfile(
            user_id=self.user_id,
            name=data.get("name"),
            age=data.get("age"),
            occupation=data.get("occupation"),
            location=data.get("location"),
            birthday=data.get("birthday"),
            hobbies=data.get("hobbies") or [],
            preferences=data.get("preferences") or {},
        )

    def _get_raw_profile(self) -> Dict:
        """生のプロフィールデータを取得"""
        try:
            result = self._supabase.table("user_profiles") \
                .select("*") \
                .eq("user_id", self.user_id) \
                .single() \
                .execute()
            return result.data or {}
        except Exception:
            return {}

    # ==================== Promise ====================

    def save_promise(self, content: str, due_date: Optional[str] = None) -> Optional[str]:
        """
        約束を保存する。

        Args:
            content: 約束の内容
            due_date: 期日（オプション）

        Returns:
            作成された約束のID
        """
        try:
            data = {
                "user_id": self.user_id,
                "content": content,
                "status": "pending",
            }
            if due_date:
                data["due_date"] = due_date

            result = self._supabase.table("promises").insert(data).execute()
            return result.data[0]["id"] if result.data else None

        except Exception as e:
            print(f"[StructuredMemory] 約束保存エラー: {e}")
            return None

    def get_promises(self, status: Optional[str] = None) -> List[Promise]:
        """
        約束一覧を取得する。

        Args:
            status: フィルタするステータス（オプション）

        Returns:
            約束のリスト
        """
        try:
            query = self._supabase.table("promises") \
                .select("*") \
                .eq("user_id", self.user_id)

            if status:
                query = query.eq("status", status)

            result = query.order("created_at", desc=True).execute()

            return [self._to_promise(d) for d in result.data]

        except Exception as e:
            print(f"[StructuredMemory] 約束取得エラー: {e}")
            return []

    def update_promise_status(self, promise_id: str, status: str) -> bool:
        """
        約束のステータスを更新する。

        Args:
            promise_id: 約束ID
            status: 新しいステータス（pending, fulfilled, broken）

        Returns:
            成功したかどうか
        """
        try:
            self._supabase.table("promises") \
                .update({"status": status}) \
                .eq("id", promise_id) \
                .eq("user_id", self.user_id) \
                .execute()
            return True

        except Exception as e:
            print(f"[StructuredMemory] 約束更新エラー: {e}")
            return False

    def _to_promise(self, data: Dict) -> Promise:
        """辞書からPromiseに変換"""
        return Promise(
            id=data.get("id", ""),
            user_id=data.get("user_id", self.user_id),
            content=data.get("content", ""),
            created_at=data.get("created_at", ""),
            due_date=data.get("due_date"),
            status=data.get("status", "pending"),
        )

    # ==================== Boundary ====================

    def save_boundary(
        self,
        content: str,
        category: str,
        severity: float = 0.5
    ) -> Optional[str]:
        """
        境界線（NG）を保存する。

        Args:
            content: NGの内容
            category: カテゴリ（topic, action, time）
            severity: 重要度（0.0-1.0）

        Returns:
            作成された境界線のID
        """
        try:
            data = {
                "user_id": self.user_id,
                "content": content,
                "category": category,
                "severity": min(1.0, max(0.0, severity)),
            }

            result = self._supabase.table("boundaries").insert(data).execute()
            return result.data[0]["id"] if result.data else None

        except Exception as e:
            print(f"[StructuredMemory] 境界線保存エラー: {e}")
            return None

    def get_boundaries(self) -> List[Boundary]:
        """
        境界線一覧を取得する。

        Returns:
            境界線のリスト
        """
        try:
            result = self._supabase.table("boundaries") \
                .select("*") \
                .eq("user_id", self.user_id) \
                .order("severity", desc=True) \
                .execute()

            return [self._to_boundary(d) for d in result.data]

        except Exception as e:
            print(f"[StructuredMemory] 境界線取得エラー: {e}")
            return []

    def check_boundary(self, text: str) -> Optional[Boundary]:
        """
        テキストが境界線に該当するかチェックする。

        Args:
            text: チェックするテキスト

        Returns:
            該当する境界線（なければNone）
        """
        boundaries = self.get_boundaries()

        for boundary in boundaries:
            # 単純な部分一致チェック
            if boundary.content in text:
                return boundary

        return None

    def _to_boundary(self, data: Dict) -> Boundary:
        """辞書からBoundaryに変換"""
        return Boundary(
            id=data.get("id", ""),
            user_id=data.get("user_id", self.user_id),
            content=data.get("content", ""),
            category=data.get("category", "topic"),
            severity=data.get("severity", 0.5),
            created_at=data.get("created_at", ""),
        )

    # ==================== Classification Integration ====================

    def process_classification(self, classification) -> None:
        """
        発話分類の結果を処理して構造化メモリに保存する。

        Args:
            classification: ClassificationResult
        """
        # confidence閾値チェック
        if classification.confidence < MIN_CONFIDENCE_THRESHOLD:
            return

        category = classification.category.value if hasattr(classification.category, 'value') else classification.category
        info = classification.extracted_info

        if category == "profile":
            self._process_profile(info)
        elif category == "promise":
            self._process_promise(info)
        elif category == "boundary":
            self._process_boundary(info)

    def _process_profile(self, info: Dict) -> None:
        """プロフィール情報を処理"""
        field_mapping = {
            "name": "name",
            "age": "age",
            "occupation": "occupation",
            "location": "location",
            "birthday": "birthday",
            "hobby": "hobby",
            "like": "hobby",  # likeもhobbyとして扱う
        }

        for key, value in info.items():
            if key in field_mapping and value:
                self.save_profile(field_mapping[key], value)

    def _process_promise(self, info: Dict) -> None:
        """約束情報を処理"""
        content = info.get("future_plan") or info.get("commitment") or info.get("explicit_promise")
        if content:
            self.save_promise(content)

    def _process_boundary(self, info: Dict) -> None:
        """境界線情報を処理"""
        # カテゴリを判定
        if "ng_topic" in info:
            self.save_boundary(info["ng_topic"], category="topic", severity=0.8)
        elif "ng_action" in info:
            self.save_boundary(info["ng_action"], category="action", severity=0.7)
        elif "sensitive_topic" in info:
            self.save_boundary(info["sensitive_topic"], category="topic", severity=0.9)
