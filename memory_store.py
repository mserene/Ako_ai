# memory_store.py
# -----------------------------------------------------------------------------
# 이 파일의 역할
# - assistant_memory.json 에 "설정(prefs)"과 "대화 기록(history)"을 저장/로드한다.
#
# 어디와 연결되나
# - local_assistant.py : JsonMemory로 규칙 학습(선호 저장) + 대화 히스토리 저장/조회
# - bot.py(디스코드)   : 같은 JSON 파일을 공유해서, 디스코드 대화도 별도 키로 저장 가능
#
# 설계 포인트
# - 저장(save)은 임시 파일(.tmp)에 먼저 쓰고, os.replace로 교체해서 "원자적 저장"을 보장한다.
# - 모든 읽기/쓰기/수정은 내부 락(_lock)으로 보호해 동시 접근 시 데이터 깨짐을 줄인다.
# -----------------------------------------------------------------------------

from __future__ import annotations

import json
import os
import time
import threading
import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List

from pathlib import Path
from typing import Optional, Callable


# -----------------------------------------------------------------------------
# 프로세스 간 파일 락
# - 디스코드 봇과 로컬 어시스턴트가 같은 JSON을 동시에 수정하므로,
#   "마지막 저장이 덮어쓰는" 경쟁 상태를 막는다.
# - discord_bot/bot.py가 쓰는 lock 파일 이름과 동일하게: assistant_memory.json.lock
# -----------------------------------------------------------------------------


class FileLock:
    def __init__(self, path: Path, timeout: float = 3.0, poll: float = 0.05):
        self.path = path
        self.timeout = timeout
        self.poll = poll
        self._fd: Optional[int] = None

    def acquire(self) -> None:
        start = time.time()
        while True:
            try:
                self._fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(self._fd, str(os.getpid()).encode("utf-8"))
                return
            except FileExistsError:
                # 너무 오래 잠겨 있으면(비정상 종료) 락을 정리
                if time.time() - start > self.timeout:
                    try:
                        self.path.unlink(missing_ok=True)
                    except Exception:
                        pass
                time.sleep(self.poll)

    def release(self) -> None:
        try:
            if self._fd is not None:
                os.close(self._fd)
        finally:
            self._fd = None
            try:
                self.path.unlink(missing_ok=True)
            except Exception:
                pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    return {}


def _save_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


# -----------------------------------------------------------------------------
# 토큰(대략) 추정/문맥 선택
# - 실제 토크나이저와 1:1로 일치하진 않지만,
#   컨텍스트 오버플로를 피하기 위한 '안전한' 보수적 추정치로 쓴다.
# - UTF-8 바이트 기준으로 4바이트 ≈ 1토큰 정도로 잡는다(대략).
# -----------------------------------------------------------------------------

def estimate_tokens_text(text: str) -> int:
    t = (text or "")
    try:
        b = t.encode("utf-8", errors="ignore")
        n = (len(b) + 3) // 4
        return int(max(1, n))
    except Exception:
        return max(1, len(t) // 4)


def estimate_tokens_message(msg: dict) -> int:
    try:
        c = str((msg or {}).get("content") or "")
    except Exception:
        c = ""
    # role/JSON 오버헤드 약간 더하기
    return 4 + estimate_tokens_text(c)


def select_tail_by_token_budget(messages, budget_tokens: int, *, min_messages: int = 4):
    """messages의 뒤쪽부터 담아 budget_tokens를 넘지 않게 선택한다."""
    if not isinstance(messages, list) or not messages:
        return []
    try:
        budget = int(budget_tokens)
    except Exception:
        budget = 0
    if budget <= 0:
        return []

    kept = []
    total = 0
    for m in reversed(messages):
        if not isinstance(m, dict):
            continue
        if m.get("role") not in ("user", "assistant"):
            continue
        t = estimate_tokens_message(m)
        # 최소 메시지 수는 보장하되, 그 이후에는 budget을 넘기면 멈춘다.
        if kept and (total + t > budget) and (len(kept) >= int(min_messages)):
            break
        kept.append({"role": str(m.get("role")), "content": str(m.get("content") or "")})
        total += t
        if total >= budget and len(kept) >= int(min_messages):
            break

    kept.reverse()
    return kept




# -----------------------------------------------------------------------------
# 기본 스키마(파일이 없거나/일부 키가 빠졌을 때 채워 넣는 기본값)
# -----------------------------------------------------------------------------
_DEFAULT: Dict[str, Any] = {
    "prefs": {
        "polite": True,
        "use_emoji": False,
        "use_heart": True,
        "heart_char": "♡",
        "persona": "ako",
        "ako_profile": {},
        "owner_user_id": "",
        # 주인님 메시지/반응 패턴(길이/문장부호/속도 등)을 누적해 톤을 맞추기 위한 프로필
        "tone_profile_owner": {},
    },
    "history": [],
    "discord_histories": {},
    "state": {},
    # AIRI 스타일(영감) 이벤트 버스: 프로세스(로컬/디스코드) 간에 알림/명령/상태를 전달
    "spark": {"queue": []},
}



def _deepcopy_default() -> Dict[str, Any]:
    # dict.copy()만 하면 내부 dict/list가 공유될 수 있어서 JSON 왕복으로 깊은 복사한다.
    return json.loads(json.dumps(_DEFAULT, ensure_ascii=False))


def _ensure_schema(data: Dict[str, Any]) -> Dict[str, Any]:
    # 파일 내용이 깨졌거나 일부 키가 없더라도 최소 스키마를 강제로 맞춘다.
    d = data if isinstance(data, dict) else {}
    defaults = _deepcopy_default()

    for k, v in defaults.items():
        if k not in d:
            d[k] = v

    if not isinstance(d.get("prefs"), dict):
        d["prefs"] = dict(defaults["prefs"])
    else:
        for pk, pv in defaults["prefs"].items():
            if pk not in d["prefs"]:
                d["prefs"][pk] = pv

    if not isinstance(d.get("history"), list):
        d["history"] = []

    if not isinstance(d.get("discord_histories"), dict):
        d["discord_histories"] = {}


    if not isinstance(d.get("state"), dict):
        d["state"] = {}

    if not isinstance(d.get("spark"), dict):
        d["spark"] = {"queue": []}
    else:
        sp = d.get("spark")
        if not isinstance(sp.get("queue"), list):
            sp["queue"] = []
        d["spark"] = sp

    return d


# -----------------------------------------------------------------------------
# JSON 메모리 저장소
# -----------------------------------------------------------------------------
@dataclass
class JsonMemory:
    path: str = "assistant_memory.json"
    max_history: int = 24

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    data: Dict[str, Any] = field(default_factory=dict, init=False)

    # in-process read cache (mtime 기반). 디스코드/로컬이 같은 파일을 읽을 때
    # 불필요한 락/파싱을 줄여서 응답 지연을 낮춘다.
    _cache_mtime: float = field(default=-1.0, init=False)

    # ----- 내부 유틸(프로세스 간 안전한 트랜잭션) -----
    def _paths(self) -> tuple[Path, Path]:
        p = Path(self.path).resolve()
        lock = p.with_suffix(p.suffix + ".lock")
        return p, lock

    def _txn(self, updater: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        """파일 락을 잡고 최신 JSON을 읽어 updater로 수정 후 저장한다."""
        p, lock = self._paths()
        with FileLock(lock):
            data = _ensure_schema(_load_json(p))
            if callable(updater):
                try:
                    updater(data)
                except Exception:
                    pass
            try:
                _save_json_atomic(p, data)
            except Exception:
                pass

        # in-memory 캐시도 갱신(동일 프로세스 내 읽기 효율)
        try:
            mtime2 = p.stat().st_mtime if p.exists() else time.time()
        except Exception:
            mtime2 = time.time()
        with self._lock:
            self.data = data
            self._cache_mtime = mtime2
        return data
    def _read(self) -> Dict[str, Any]:
        p, lock = self._paths()

        # 빠른 경로: 파일 mtime이 안 바뀌었으면 캐시를 그대로 반환
        try:
            mtime = p.stat().st_mtime if p.exists() else -1.0
        except Exception:
            mtime = -1.0

        with self._lock:
            if isinstance(self.data, dict) and self.data and self._cache_mtime == mtime:
                return self.data

        # 느린 경로: 파일 재로드
        data = _ensure_schema(_load_json(p))
        if not isinstance(data, dict) or not data:
            # 드물게 replace 타이밍/권한 문제로 읽기 실패할 수 있어 락으로 한 번 더 시도
            try:
                with FileLock(lock):
                    data = _ensure_schema(_load_json(p))
            except Exception:
                data = _deepcopy_default()

        try:
            mtime2 = p.stat().st_mtime if p.exists() else -1.0
        except Exception:
            mtime2 = mtime

        with self._lock:
            self.data = data
            self._cache_mtime = mtime2
        return data

    # ----- 파일 I/O -----
    def load(self) -> None:
        self._read()

    def save(self) -> None:
        # self.data를 그대로 저장하는 경우에도 락을 잡고 최신 파일을 기준으로 병합한다.
        def _u(d: Dict[str, Any]) -> None:
            # 현재 캐시 내용을 최신 파일에 덮어쓰기(단, spark/state 등은 누락 방지 위해 스키마 유지)
            with self._lock:
                cur = dict(self.data) if isinstance(self.data, dict) else {}
            cur = _ensure_schema(cur)
            d.clear()
            d.update(cur)
        self._txn(_u)

    # ----- prefs -----
    def get_prefs(self) -> Dict[str, Any]:
        data = self._read()
        prefs = data.get("prefs") or {}
        return dict(prefs) if isinstance(prefs, dict) else {}

    def set_pref(self, key: str, value: Any) -> None:
        def _u(d: Dict[str, Any]) -> None:
            prefs = d.get("prefs")
            if not isinstance(prefs, dict):
                prefs = {}
            prefs[str(key)] = value
            d["prefs"] = prefs
        self._txn(_u)


    # ---- state (로컬/디스코드 공용 런타임 상태) ----
    def get_state(self) -> Dict[str, Any]:
        data = self._read()
        st = data.get("state")
        return dict(st) if isinstance(st, dict) else {}

    def set_state(self, key: str, value: Any) -> None:
        def _u(d: Dict[str, Any]) -> None:
            st = d.get("state")
            if not isinstance(st, dict):
                st = {}
            st[str(key)] = value
            d["state"] = st
        self._txn(_u)

    def update_state(self, fn) -> None:
        def _u(d: Dict[str, Any]) -> None:
            st = d.get("state")
            if not isinstance(st, dict):
                st = {}
            try:
                new_st = fn(dict(st))
            except Exception:
                new_st = None
            d["state"] = new_st if isinstance(new_st, dict) else st
        self._txn(_u)

    # ----- history -----
    def append_history(self, role: str, content: str) -> None:
        if not content:
            return
        msg = {"role": str(role), "content": str(content)}

        def _u(d: Dict[str, Any]) -> None:
            hist = d.get("history")
            if not isinstance(hist, list):
                hist = []
            hist.append(msg)
            limit = int(self.max_history)
            if limit > 0 and len(hist) > limit:
                hist = hist[-limit:]
            d["history"] = hist
        self._txn(_u)

    def recent_messages(self, max_messages: int = 12) -> List[Dict[str, str]]:
        data = self._read()
        hist = data.get("history")
        if not isinstance(hist, list):
            return []
        return list(hist[-int(max_messages):])


    # ----- raw access (discord/local 공용) -----
    def read_all(self) -> Dict[str, Any]:
        """현재 전체 메모리 스냅샷(깊은 복사본)을 반환한다."""
        data = self._read()
        try:
            return copy.deepcopy(data)
        except Exception:
            # deepcopy가 실패해도 최소한 dict는 돌려준다.
            return dict(data) if isinstance(data, dict) else {}

    def update_all(self, update_fn) -> None:
        """파일 락을 잡고 전체 메모리를 update_fn으로 수정해 저장한다."""
        if not callable(update_fn):
            return
        def _u(d: Dict[str, Any]) -> None:
            update_fn(d)
        self._txn(_u)

    def get_history_messages(self, *, max_messages_cap: int = 0) -> List[Dict[str, str]]:
        data = self._read()
        hist = data.get("history")
        if not isinstance(hist, list):
            return []
        msgs = [m for m in hist if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
        if max_messages_cap and len(msgs) > int(max_messages_cap):
            msgs = msgs[-int(max_messages_cap):]
        return [{"role": str(m.get("role")), "content": str(m.get("content") or "")} for m in msgs]

    def get_discord_history_messages(self, user_id: int, *, max_messages_cap: int = 0) -> List[Dict[str, str]]:
        data = self._read()
        dh = data.get("discord_histories")
        if not isinstance(dh, dict):
            return []
        hist = dh.get(str(user_id))
        if not isinstance(hist, list):
            return []
        msgs = [m for m in hist if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
        if max_messages_cap and len(msgs) > int(max_messages_cap):
            msgs = msgs[-int(max_messages_cap):]
        return [{"role": str(m.get("role")), "content": str(m.get("content") or "")} for m in msgs]

    def append_discord_history(self, user_id: int, role: str, content: str, *, max_turns: int = 40) -> None:
        if not content:
            return
        msg = {"role": str(role), "content": str(content)}

        def _u(d: Dict[str, Any]) -> None:
            dh = d.get("discord_histories")
            if not isinstance(dh, dict):
                dh = {}
            key = str(user_id)
            hist = dh.get(key)
            if not isinstance(hist, list):
                hist = []
            hist.append(msg)
            mt = max(10, int(max_turns))
            max_msgs = mt * 2
            if max_msgs > 0 and len(hist) > max_msgs:
                hist = hist[-max_msgs:]
            dh[key] = hist
            d["discord_histories"] = dh
        self._txn(_u)

    def context_messages_by_budget(
        self,
        messages: List[Dict[str, str]],
        *,
        budget_tokens: int,
        min_messages: int = 4,
    ) -> List[Dict[str, str]]:
        return select_tail_by_token_budget(messages, int(budget_tokens), min_messages=int(min_messages))
