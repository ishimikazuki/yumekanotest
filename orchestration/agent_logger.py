"""AIエージェントのログ管理システム。

各エージェント(Observer, Actor, Critic)の処理を記録し、
デバッグやモニタリングに利用する。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import deque
import threading


@dataclass
class AgentLog:
    """個々のエージェントログエントリ"""
    timestamp: str
    agent_name: str  # "observer", "actor", "critic"
    action: str  # "start", "end", "error"
    duration_ms: Optional[float] = None
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AgentLogger:
    """エージェントログの管理クラス（シングルトン）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_logs: int = 100):
        if self._initialized:
            return
        self._initialized = True
        self.logs: deque = deque(maxlen=max_logs)
        self._current_turn: Dict[str, AgentLog] = {}
        self._turn_start_times: Dict[str, float] = {}
        self._console_output = True  # コンソール出力フラグ

    def enable_console(self, enabled: bool = True):
        """コンソール出力を有効/無効にする"""
        self._console_output = enabled

    def start_agent(
        self,
        agent_name: str,
        input_data: Any,
        model: Optional[str] = None,
        provider: Optional[str] = None
    ):
        """エージェント処理開始のログ"""
        self._turn_start_times[agent_name] = time.time()

        # 入力のサマリー作成
        input_summary = self._summarize(input_data, max_len=200)

        log = AgentLog(
            timestamp=datetime.utcnow().isoformat() + "Z",
            agent_name=agent_name,
            action="start",
            input_summary=input_summary,
            model=model,
            provider=provider,
        )
        self._current_turn[agent_name] = log

        if self._console_output:
            print(f"[{agent_name.upper()}] 開始 | モデル: {model} | Provider: {provider}")
            print(f"  入力: {input_summary[:100]}...")

    def end_agent(
        self,
        agent_name: str,
        output_data: Any,
        details: Optional[Dict[str, Any]] = None
    ):
        """エージェント処理完了のログ"""
        start_time = self._turn_start_times.get(agent_name, time.time())
        duration_ms = (time.time() - start_time) * 1000

        output_summary = self._summarize(output_data, max_len=300)

        log = AgentLog(
            timestamp=datetime.utcnow().isoformat() + "Z",
            agent_name=agent_name,
            action="end",
            duration_ms=round(duration_ms, 2),
            output_summary=output_summary,
            details=details or {},
        )

        # 開始ログの情報を引き継ぐ
        if agent_name in self._current_turn:
            start_log = self._current_turn[agent_name]
            log.input_summary = start_log.input_summary
            log.model = start_log.model
            log.provider = start_log.provider

        self.logs.append(log)

        if self._console_output:
            print(f"[{agent_name.upper()}] 完了 | 所要時間: {duration_ms:.0f}ms")
            print(f"  出力: {output_summary[:100]}...")

        # クリーンアップ
        self._current_turn.pop(agent_name, None)
        self._turn_start_times.pop(agent_name, None)

    def error_agent(
        self,
        agent_name: str,
        error: Exception,
        details: Optional[Dict[str, Any]] = None
    ):
        """エージェントエラーのログ"""
        start_time = self._turn_start_times.get(agent_name, time.time())
        duration_ms = (time.time() - start_time) * 1000

        log = AgentLog(
            timestamp=datetime.utcnow().isoformat() + "Z",
            agent_name=agent_name,
            action="error",
            duration_ms=round(duration_ms, 2),
            error=f"{type(error).__name__}: {str(error)}",
            details=details or {},
        )

        if agent_name in self._current_turn:
            start_log = self._current_turn[agent_name]
            log.input_summary = start_log.input_summary
            log.model = start_log.model
            log.provider = start_log.provider

        self.logs.append(log)

        if self._console_output:
            print(f"[{agent_name.upper()}] エラー | 所要時間: {duration_ms:.0f}ms")
            print(f"  エラー: {log.error}")

        self._current_turn.pop(agent_name, None)
        self._turn_start_times.pop(agent_name, None)

    def get_recent_logs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """最近のログを取得"""
        logs_list = list(self.logs)
        return [log.to_dict() for log in logs_list[-limit:]]

    def get_logs_by_agent(self, agent_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """特定エージェントのログを取得"""
        filtered = [log for log in self.logs if log.agent_name == agent_name]
        return [log.to_dict() for log in filtered[-limit:]]

    def clear_logs(self):
        """ログをクリア"""
        self.logs.clear()
        self._current_turn.clear()
        self._turn_start_times.clear()

    def _summarize(self, data: Any, max_len: int = 200) -> str:
        """データのサマリーを生成"""
        if data is None:
            return "None"
        if isinstance(data, str):
            return data[:max_len]
        if isinstance(data, dict):
            try:
                json_str = json.dumps(data, ensure_ascii=False)
                return json_str[:max_len]
            except:
                return str(data)[:max_len]
        if isinstance(data, list):
            return f"[{len(data)} items]"
        return str(data)[:max_len]


# グローバルインスタンス
agent_logger = AgentLogger()
