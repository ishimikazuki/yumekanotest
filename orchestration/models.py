"""ドメインモデル定義（外部依存なし）。"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional


def utc_now() -> str:
    """UTC 時刻を ISO 形式で返す。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class EmotionState:
    # PAD Model (Pleasure, Arousal, Dominance) -10.0 to +10.0
    pleasure: float = 0.0   # 快 (+10) - 不快 (-10)
    arousal: float = 0.0    # 覚醒 (+10) - 沈静 (-10)
    dominance: float = 0.0  # 支配 (+10) - 服従 (-10)

    def clamp(self) -> None:
        self.pleasure = max(-10.0, min(10.0, self.pleasure))
        self.arousal = max(-10.0, min(10.0, self.arousal))
        self.dominance = max(-10.0, min(10.0, self.dominance))
    
    def decay(self, rate: float = 0.5) -> None:
        """感情の減衰（0に近づく）"""
        self.pleasure *= (1.0 - rate * 0.1)
        self.arousal *= (1.0 - rate * 0.1)
        # Dominanceは性格依存が強いので減衰させない、あるいは緩やかにする


@dataclass
class ScenarioState:
    current_phase: str = "phase_1_meeting"
    current_scene: str = "scene_station_front"
    turn_count_in_phase: int = 0
    variables: Dict[str, Any] = field(default_factory=dict)  # フラグや数値変数

@dataclass
class UserState:
    user_id: str
    updated_at: str
    emotion: EmotionState = field(default_factory=EmotionState)
    scenario: ScenarioState = field(default_factory=ScenarioState)
    # long_term_memories は Vector DB 側に移行するため、ここでの保持は「直近のキャッシュ」的な扱い、あるいは削除でも良いが
    # 一旦互換性のため残すか、Actorへの注入用として使う。
    # ここでは「Actorに渡すべき重要なメモ」として残す。
    current_context_memories: List[str] = field(default_factory=list)

    @classmethod
    def new(cls, user_id: str) -> "UserState":
        return cls(user_id=user_id, updated_at=utc_now())

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "UserState":
        emo = data.get("emotion", data.get("biometrics", {})) # 旧 biometrics からの移行互換
        scen = data.get("scenario", {})
        
        # 旧 mood などを PAD に簡易変換
        pleasure = emo.get("pleasure", emo.get("mood", 0.0))
        arousal = emo.get("arousal", emo.get("energy", 0.0) / 10.0 if "energy" in emo else 0.0)
        dominance = emo.get("dominance", 0.0)

        return cls(
            user_id=data["user_id"],
            updated_at=data.get("updated_at", utc_now()),
            emotion=EmotionState(
                pleasure=float(pleasure),
                arousal=float(arousal),
                dominance=float(dominance)
            ),
            scenario=ScenarioState(
                current_phase=scen.get("current_phase", "phase_1_meeting"),
                current_scene=scen.get("current_scene", "scene_station_front"),
                turn_count_in_phase=scen.get("turn_count_in_phase", 0),
                variables=scen.get("variables", scen.get("flags", {})),
            ),
            current_context_memories=list(data.get("current_context_memories", data.get("long_term_memories", []))),
        )


@dataclass
class ObservationResult:
    updated_state: UserState
    instruction_override: Optional[str] = None
