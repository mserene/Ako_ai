from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip().lower())


def _strip_quotes(text: str) -> str:
    text = _normalize(text)
    pairs = [
        ("'", "'"), ('"', '"'), ("“", "”"), ("‘", "’"), ("`", "`"),
        ("「", "」"), ("『", "』"),
    ]
    for left, right in pairs:
        if text.startswith(left) and text.endswith(right):
            return text[1:-1].strip()
    return text.strip()


def _clean_phrase(text: str) -> str:
    text = _strip_quotes(text)
    text = re.sub(r"^(내가|주인님이)\s+", "", text).strip()
    return text


def _clean_meaning(text: str) -> str:
    text = _normalize(text)
    text = re.sub(r"(?:라고|이라고)?\s*(?:기억해|기억해줘|기억해둬|이해해|받아들여)\s*$", "", text).strip()
    text = re.sub(r"(?:라는\s*)?(?:뜻|의미|표현|말)\s*$", "", text).strip()
    return text


@dataclass
class JsonMemoryStore:
    """Ako 장기 기억 저장소.

    원칙:
    - 저장된 단어를 코드에서 바로 답변하지 않는다.
    - 장기 기억은 모델이 참고할 컨텍스트로만 제공한다.
    - 사용자가 명확히 교정하거나 의미를 알려준 말만 저장한다.
    """

    path: Path = field(default_factory=lambda: _app_root() / "memory_state.json")

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if not self.path.exists():
            self._write(self._default_state())

    @staticmethod
    def _default_state() -> dict[str, Any]:
        now = _now_iso()
        return {
            "version": 4,
            "profile": {
                "owner_name": "주인님",
                "assistant_name": "아코",
                "tone": "다정하지만 유용한 로컬 AI 비서",
                "emoji_rule": "이모지 대신 필요할 때 ♡만 사용",
                "memory_policy": "저장된 단어를 코드로 즉답하지 말고, 모델이 참고하게만 한다.",
            },
            "facts": [
                {
                    "text": "주인님은 Ako를 텍스트 대화, 음성 대화, 화면 인식, 앱 조작이 가능한 로컬 AI 비서로 만들고 있다.",
                    "created_at": now,
                    "updated_at": now,
                    "use_count": 0,
                },
                {
                    "text": "주인님은 키워드별 고정 응답을 싫어한다. 기억은 모델이 참고하는 방식으로만 사용해야 한다.",
                    "created_at": now,
                    "updated_at": now,
                    "use_count": 0,
                },
            ],
            "preferences": [
                {
                    "text": "주인님은 키워드처럼 바로 튀어나오는 고정 응답 방식을 싫어한다.",
                    "created_at": now,
                    "updated_at": now,
                    "use_count": 0,
                }
            ],
            "interpretation_rules": [],
            "corrections": [],
        }

    def load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            data = self._default_state()

        default = self._default_state()
        for key, value in default.items():
            data.setdefault(key, value)
        data.setdefault("profile", default["profile"])

        # 중요한 전역 취향은 중복 없이 보강
        self._ensure_global_memory(data)
        return data

    def _ensure_global_memory(self, data: dict[str, Any]) -> None:
        prefs = data.setdefault("preferences", [])
        fact_texts = {str(item.get("text", "")) for item in data.setdefault("facts", [])}
        pref_texts = {str(item.get("text", "")) for item in prefs}

        now = _now_iso()
        fixed_pref = "주인님은 키워드처럼 바로 튀어나오는 고정 응답 방식을 싫어한다."
        fixed_fact = "주인님은 키워드별 고정 응답을 싫어한다. 기억은 모델이 참고하는 방식으로만 사용해야 한다."

        if fixed_pref not in pref_texts:
            prefs.append({"text": fixed_pref, "created_at": now, "updated_at": now, "use_count": 0})
        if fixed_fact not in fact_texts:
            data["facts"].append({"text": fixed_fact, "created_at": now, "updated_at": now, "use_count": 0})

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=self.path.name + ".",
            suffix=".tmp",
            dir=str(self.path.parent),
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(tmp_name, self.path)
        finally:
            try:
                if os.path.exists(tmp_name):
                    os.remove(tmp_name)
            except Exception:
                pass

    def save(self, data: dict[str, Any]) -> None:
        self._write(data)

    def _upsert_list_item(
        self,
        data: dict[str, Any],
        section: str,
        item: dict[str, Any],
        unique_key: str | None = None,
    ) -> None:
        items = data.setdefault(section, [])
        now = _now_iso()
        item.setdefault("created_at", now)
        item["updated_at"] = now
        item.setdefault("use_count", 0)

        if unique_key and item.get(unique_key):
            target = _compact(str(item[unique_key]))
            for old in items:
                if _compact(str(old.get(unique_key, ""))) == target:
                    old.update(item)
                    return

        items.append(item)

    def _save_rule(self, raw: str, phrase: str, meaning: str) -> str | None:
        phrase = _clean_phrase(phrase)
        meaning = _clean_meaning(meaning)

        if not phrase or not meaning:
            return None
        if len(phrase) > 40 or len(meaning) > 160:
            return None

        data = self.load()
        self._upsert_list_item(
            data,
            "interpretation_rules",
            {
                "phrase": phrase,
                "meaning": meaning,
                "response_style": "모델이 이 의미를 참고해서 자연스럽게 답한다. 코드에서 고정 응답으로 바로 처리하지 않는다.",
                "source": raw,
            },
            unique_key="phrase",
        )
        self.save(data)

        return f"기억했어요, 주인님♡ 다음부터 '{phrase}'는 {meaning}로 참고할게요."

    def remember_interaction(self, user_text: str) -> str | None:
        raw = _normalize(user_text)
        if not raw:
            return None

        patterns = [
            r"(?:아니지\s*)?(?:방금\s*)?내가\s*[\"'“”‘’`]?(.+?)[\"'“”‘’`]?\s*(?:라고|이라고)\s*(?:말한\s*건|말하는\s*건|부르는\s*건|부른\s*건|하는\s*건|한\s*건)\s*(.+?)(?:야|이야|라고|이라는\s*뜻이야|라는\s*뜻이야|라는\s*의미야)?$",
            r"(?:아니지\s*)?(?:방금\s*)?[\"'“”‘’`]?(.+?)[\"'“”‘’`]?\s*(?:라고|이라고)\s*(?:하면|말하면|부르면)\s*(.+?)(?:로|라고)?\s*(?:이해해|받아들여|기억해)?$",
            r"(?:앞으로|다음부터)\s*(?:내가\s*)?[\"'“”‘’`]?(.+?)[\"'“”‘’`]?\s*(?:라고|이라고)?\s*(?:하면|말하면|부르면)\s*(.+?)(?:로|라고)?\s*(?:이해해|받아들여|기억해)$",
            r"[\"'“”‘’`]?(.+?)[\"'“”‘’`]?\s*(?:은|는)\s*(.+?)(?:라는\s*)?(?:뜻|의미|표현|말)(?:이야|야|으로\s*기억해)?$",
        ]

        for pat in patterns:
            m = re.search(pat, raw)
            if m:
                reply = self._save_rule(raw, m.group(1), m.group(2))
                if reply:
                    return reply

        m = re.search(r"나는\s+(.+?)\s*(좋아해|싫어해|선호해|별로야|불편해)$", raw)
        if m:
            target = _normalize(m.group(1))
            sentiment = m.group(2)
            if target:
                data = self.load()
                pref_text = f"주인님은 {target}을/를 {sentiment}."
                self._upsert_list_item(
                    data,
                    "preferences",
                    {"text": pref_text, "source": raw},
                    unique_key="text",
                )
                self.save(data)
                return "취향으로 기억해둘게요, 주인님♡"

        if "기억해" in raw or "기억해둬" in raw or "잊지마" in raw:
            cleaned = raw
            cleaned = re.sub(r"^(이건|이거|앞으로|다음부터)\s*", "", cleaned).strip()
            cleaned = re.sub(r"(기억해줘|기억해둬|기억해|잊지마)\s*$", "", cleaned).strip()
            if cleaned and len(cleaned) >= 3:
                data = self.load()
                self._upsert_list_item(
                    data,
                    "facts",
                    {"text": cleaned, "source": raw},
                    unique_key="text",
                )
                self.save(data)
                return "기억해둘게요, 주인님♡"

        return None

    def get_relevant_memories(self, user_text: str, limit: int = 8) -> list[str]:
        data = self.load()
        raw = _normalize(user_text)
        compact_user = _compact(raw)

        scored: list[tuple[int, str, str, dict[str, Any]]] = []

        for item in data.get("interpretation_rules", []):
            phrase = str(item.get("phrase", "")).strip()
            meaning = str(item.get("meaning", "")).strip()
            response_style = str(item.get("response_style", "")).strip()
            if not phrase or not meaning:
                continue

            score = 0
            if _compact(phrase) and _compact(phrase) in compact_user:
                score += 150
            if phrase and phrase in raw:
                score += 150

            if score:
                line = f"'{phrase}'은/는 {meaning}. {response_style}".strip()
                scored.append((score, "interpretation_rules", line, item))

        tokens = {tok for tok in re.split(r"[\s,.;:!?()\[\]{}'\"“”‘’`]+", raw) if len(tok) >= 2}
        for section in ("preferences", "facts", "corrections"):
            for item in data.get(section, []):
                text = str(item.get("text") or item.get("correct") or "").strip()
                if not text:
                    continue

                score = 0
                for tok in tokens:
                    if tok and tok in text:
                        score += 8

                if "키워드" in text or "고정 응답" in text:
                    score += 5

                if score > 0:
                    scored.append((score, section, text, item))

        scored.sort(key=lambda x: x[0], reverse=True)

        result: list[str] = []
        used = set()
        for _score, _section, line, item in scored[:limit]:
            if line in used:
                continue
            used.add(line)
            result.append(line)
            item["use_count"] = int(item.get("use_count", 0) or 0) + 1
            item["last_used_at"] = _now_iso()

        if result:
            self.save(data)

        return result

    def build_memory_prompt(self, user_text: str) -> str:
        memories = self.get_relevant_memories(user_text)
        if not memories:
            return ""

        lines = [
            "장기 기억:",
            "- 아래 기억은 주인님이 알려준 개인화 규칙이다.",
            "- 절대 저장된 단어를 코드식 키워드 응답처럼 반복하지 마.",
            "- 관련 기억은 답변에 자연스럽게 반영하되, 기억 목록을 그대로 읊지 마.",
            "- 현재 사용자 말이 기억과 충돌하면 현재 사용자 말이 우선이다.",
        ]
        for memory in memories:
            lines.append(f"- {memory}")
        return "\n".join(lines)
