# memory_store.py
# -----------------------------------------------------------------------------
# 어시스턴트 메모리 저장/로드 관리
#
# 구조 개선:
# - assistant_memory.json : 대화 히스토리, 상태값 (일반 데이터)
# - assistant_prefs.json  : 페르소나/주인 설정 등 민감 설정 (별도 파일)
#
# 이렇게 분리하면:
# - memory.json은 Git에 올려도 됨 (대화 내용 제외 시)
# - prefs.json은 .gitignore에 추가해서 유출 방지
# -----------------------------------------------------------------------------
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 기본 파일 경로
_DEFAULT_MEMORY_FILE = "assistant_memory.json"
_DEFAULT_PREFS_FILE = "assistant_prefs.json"

# 최대 보관 히스토리 (무한정 쌓이면 파일이 커짐)
_MAX_HISTORY = 200
_MAX_DISCORD_HISTORY_PER_CHANNEL = 50


def _safe_load(path: str) -> Dict:
    """JSON 파일을 안전하게 로드. 실패 시 빈 dict 반환."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        logger.warning(f"JSON 파싱 오류 ({path}): {e} → 빈 데이터로 시작")
        # 손상된 파일은 백업 후 초기화
        _backup_corrupted(path)
        return {}
    except Exception as e:
        logger.error(f"파일 로드 실패 ({path}): {e}")
        return {}


def _safe_save(path: str, data: Dict) -> bool:
    """JSON 파일을 안전하게 저장. 임시 파일 → 원본 교체 방식으로 손상 방지."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.move(tmp, path)
        return True
    except Exception as e:
        logger.error(f"파일 저장 실패 ({path}): {e}")
        # 임시 파일 정리
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False


def _backup_corrupted(path: str):
    """손상된 파일을 백업."""
    try:
        backup = path + f".corrupted.{int(time.time())}"
        shutil.copy2(path, backup)
        logger.info(f"손상된 파일 백업: {backup}")
    except Exception:
        pass


def _trim_history(history: list, max_count: int) -> list:
    """히스토리가 너무 길면 오래된 것부터 잘라냄."""
    if len(history) > max_count:
        return history[-max_count:]
    return history


# -----------------------------------------------------------------------------
# MemoryStore 클래스
# -----------------------------------------------------------------------------
class MemoryStore:
    """
    대화 메모리 및 설정을 관리하는 클래스.

    사용법:
        store = MemoryStore()
        store.add_history("user", "안녕")
        store.save()
    """

    def __init__(
        self,
        memory_path: str = _DEFAULT_MEMORY_FILE,
        prefs_path: str = _DEFAULT_PREFS_FILE,
    ):
        self.memory_path = memory_path
        self.prefs_path = prefs_path

        # 데이터 로드
        raw_memory = _safe_load(memory_path)
        raw_prefs = _safe_load(prefs_path)

        # 기존 단일 파일 구조에서 마이그레이션 지원
        # (assistant_memory.json 안에 prefs가 있으면 prefs.json으로 분리)
        if "prefs" in raw_memory and not raw_prefs:
            logger.info("[MEMORY] prefs를 별도 파일로 마이그레이션")
            raw_prefs = raw_memory.pop("prefs")
            _safe_save(prefs_path, raw_prefs)
            _safe_save(memory_path, raw_memory)

        self.history: list = raw_memory.get("history", [])
        self.discord_histories: Dict[str, list] = raw_memory.get("discord_histories", {})
        self.state: Dict = raw_memory.get("state", {})
        self.spark: Dict = raw_memory.get("spark", {"queue": []})

        # 민감 설정은 별도 관리
        self.prefs: Dict = raw_prefs

    # ---- 일반 대화 히스토리 ----
    def add_history(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        self.history = _trim_history(self.history, _MAX_HISTORY)

    def get_history(self) -> list:
        return list(self.history)

    def clear_history(self):
        self.history = []

    # ---- Discord 채널별 히스토리 ----
    def add_discord_history(self, channel_id: str, role: str, content: str):
        ch = str(channel_id)
        if ch not in self.discord_histories:
            self.discord_histories[ch] = []
        self.discord_histories[ch].append({"role": role, "content": content})
        self.discord_histories[ch] = _trim_history(
            self.discord_histories[ch], _MAX_DISCORD_HISTORY_PER_CHANNEL
        )

    def get_discord_history(self, channel_id: str) -> list:
        return list(self.discord_histories.get(str(channel_id), []))

    def clear_discord_history(self, channel_id: str):
        ch = str(channel_id)
        if ch in self.discord_histories:
            self.discord_histories[ch] = []

    # ---- 상태 ----
    def get_state(self, key: str, default=None):
        return self.state.get(key, default)

    def set_state(self, key: str, value):
        self.state[key] = value

    # ---- 설정 접근 (prefs는 별도 파일) ----
    def get_pref(self, key: str, default=None):
        return self.prefs.get(key, default)

    def set_pref(self, key: str, value):
        self.prefs[key] = value

    # ---- 저장 ----
    def save(self) -> bool:
        """메모리(대화/상태)와 설정을 각각 저장."""
        memory_data = {
            "history": self.history,
            "discord_histories": self.discord_histories,
            "state": self.state,
            "spark": self.spark,
        }
        ok1 = _safe_save(self.memory_path, memory_data)
        ok2 = _safe_save(self.prefs_path, self.prefs)

        if not ok1:
            logger.error("메모리 저장 실패")
        if not ok2:
            logger.error("설정 저장 실패")
        return ok1 and ok2

    def save_prefs_only(self) -> bool:
        return _safe_save(self.prefs_path, self.prefs)


# -----------------------------------------------------------------------------
# 전역 싱글턴 (기존 코드 호환용)
# -----------------------------------------------------------------------------
_store: Optional[MemoryStore] = None


def get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store


def reload_store():
    """메모리를 디스크에서 다시 로드."""
    global _store
    _store = MemoryStore()
    return _store
