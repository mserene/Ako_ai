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
    """개발/빌드 실행 모두에서 앱 루트 폴더를 찾는다."""
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
    if len(text) >= 2 and text[0] in "\"'“”‘’`" and text[-1] in "\"'“”‘’`":
        return text[1:-1].strip()
    return text


@dataclass
class JsonMemoryStore:
    """Ako 장기 기억 저장소.

    원칙:
    - 모든 대화를 무작정 저장하지 않는다.
    - 사용자가 '기억해', '뜻이야', '의미야', '다음부터'처럼 명확하게 알려준 것만 저장한다.
    - 대화에 관련된 기억만 시스템 프롬프트에 넣는다.
    """

    path: Path = field(default_factory=lambda: _app_root() / "memory_state.json")

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if not self.path.exists():
            self._write(self._default_state())

    @staticmethod
    def _default_state() -> dict[str, Any]:
        return {
            "version": 1,
            "profile": {
                "owner_name": "주인님",
                "assistant_name": "아코",
                "tone": "다정하지만 유용한 로컬 AI 비서",
                "emoji_rule": "이모지 대신 필요할 때 ♡만 사용",
            },
            "facts": [
                {
                    "text": "주인님은 Ako를 텍스트 대화, 음성 대화, 화면 인식, 앱 조작이 가능한 로컬 AI 비서로 만들고 있다.",
                    "created_at": _now_iso(),
                    "updated_at": _now_iso(),
                    "use_count": 0,
                }
            ],
            "preferences": [],
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
        return data

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
    ) -> bool:
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
                    return True

        items.append(item)
        return True

    def remember_interaction(self, user_text: str) -> str | None:
        """사용자 문장에서 명시적 기억/교정 의도를 찾아 저장한다.

        반환값:
        - 저장했으면 사용자에게 보여줄 짧은 답변
        - 저장할 내용이 아니면 None
        """
        raw = _normalize(user_text)
        if not raw:
            return None

        data = self.load()

        # 예: 방금 내가 '굿'이라고 말한건 널 칭찬한거야
        m = re.search(
            r"(?:방금\s*)?내가\s*[\"'“”‘’`]?(.+?)[\"'“”‘’`]?\s*(?:라고|이라고)\s*말한\s*건?\s*(.+?)(?:야|이야|라는\s*뜻이야|라는\s*의미야|로\s*이해해)?$",
            raw,
        )
        if m:
            phrase = _strip_quotes(m.group(1))
            meaning = _normalize(m.group(2))
            if phrase and meaning and len(phrase) <= 40:
                self._upsert_list_item(
                    data,
                    "interpretation_rules",
                    {
                        "phrase": phrase,
                        "meaning": meaning,
                        "response_style": "그 의미를 반영해서 자연스럽게 반응한다.",
                        "source": raw,
                    },
                    unique_key="phrase",
                )
                self.save(data)
                return f"기억해둘게요, 주인님♡ 다음부터 '{phrase}'는 {meaning}로 받아들일게요."

        # 예: 다음부터 내가 '굿'이라고 하면 널 칭찬하는 뜻으로 이해해
        m = re.search(
            r"(?:앞으로|다음부터)\s*(?:내가\s*)?[\"'“”‘’`]?(.+?)[\"'“”‘’`]?\s*(?:라고|이라고)?\s*(?:하면|말하면)\s*(.+?)(?:로|라고)?\s*(?:이해해|받아들여|기억해)$",
            raw,
        )
        if m:
            phrase = _strip_quotes(m.group(1))
            meaning = _normalize(m.group(2))
            if phrase and meaning and len(phrase) <= 40:
                self._upsert_list_item(
                    data,
                    "interpretation_rules",
                    {
                        "phrase": phrase,
                        "meaning": meaning,
                        "response_style": "그 의미를 반영해서 자연스럽게 반응한다.",
                        "source": raw,
                    },
                    unique_key="phrase",
                )
                self.save(data)
                return f"알겠어요, 주인님♡ 다음부터 '{phrase}'는 {meaning}로 이해할게요."

        # 예: '굿'은 널 칭찬하는 뜻이야 / 굿은 칭찬이야
        m = re.search(
            r"[\"'“”‘’`]?(.+?)[\"'“”‘’`]?\s*(?:은|는)\s*(.+?)(?:라는\s*)?(?:뜻|의미|표현|말)(?:이야|야|으로\s*기억해)?$",
            raw,
        )
        if m and any(k in raw for k in ("뜻", "의미", "표현", "말", "기억")):
            phrase = _strip_quotes(m.group(1))
            meaning = _normalize(m.group(2))
            if phrase and meaning and len(phrase) <= 40:
                self._upsert_list_item(
                    data,
                    "interpretation_rules",
                    {
                        "phrase": phrase,
                        "meaning": meaning,
                        "response_style": "그 의미를 반영해서 자연스럽게 반응한다.",
                        "source": raw,
                    },
                    unique_key="phrase",
                )
                self.save(data)
                return f"기억했어요, 주인님♡ '{phrase}'는 {meaning}라는 뜻으로 받아들일게요."

        # 예: 나는 너무 딱딱한 말투 싫어해 / 나는 하트 좋아해
        m = re.search(r"나는\s+(.+?)\s*(좋아해|싫어해|선호해|별로야|불편해)$", raw)
        if m:
            target = _normalize(m.group(1))
            sentiment = m.group(2)
            if target:
                pref_text = f"주인님은 {target}을/를 {sentiment}."
                self._upsert_list_item(
                    data,
                    "preferences",
                    {
                        "text": pref_text,
                        "source": raw,
                    },
                    unique_key="text",
                )
                self.save(data)
                return "취향으로 기억해둘게요, 주인님♡"

        # 예: 앞으로 대답은 더 짧게 해 / 이건 기억해
        if "기억해" in raw or "기억해둬" in raw or "잊지마" in raw:
            cleaned = raw
            cleaned = re.sub(r"^(이건|이거|앞으로|다음부터)\s*", "", cleaned).strip()
            cleaned = re.sub(r"(기억해줘|기억해둬|기억해|잊지마)\s*$", "", cleaned).strip()
            if cleaned and len(cleaned) >= 3:
                self._upsert_list_item(
                    data,
                    "facts",
                    {
                        "text": cleaned,
                        "source": raw,
                    },
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

        # 해석 규칙은 phrase가 직접 포함되면 강하게 반영
        for item in data.get("interpretation_rules", []):
            phrase = str(item.get("phrase", "")).strip()
            meaning = str(item.get("meaning", "")).strip()
            response_style = str(item.get("response_style", "")).strip()
            if not phrase or not meaning:
                continue

            score = 0
            if _compact(phrase) and _compact(phrase) in compact_user:
                score += 100
            if phrase and phrase in raw:
                score += 100

            if score:
                line = f"'{phrase}'은/는 {meaning}. {response_style}".strip()
                scored.append((score, "interpretation_rules", line, item))

        # preferences/facts/corrections는 단어 겹침 기반으로 약하게 반영
        tokens = {tok for tok in re.split(r"[\s,.;:!?()\[\]{}'\"“”‘’`]+", raw) if len(tok) >= 2}
        for section in ("preferences", "facts", "corrections"):
            for item in data.get(section, []):
                text = str(item.get("text") or item.get("correct") or "").strip()
                if not text:
                    continue

                score = 0
                compact_text = _compact(text)
                for tok in tokens:
                    if tok and tok in text:
                        score += 8
                if compact_user and compact_user in compact_text:
                    score += 20

                # 기본 프로필성 기억은 초반에 조금씩 넣어준다.
                if section in ("preferences", "facts"):
                    score += 1

                if score > 0:
                    scored.append((score, section, text, item))

        scored.sort(key=lambda x: x[0], reverse=True)

        result: list[str] = []
        used = set()
        for _score, section, line, item in scored[:limit]:
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
            "- 관련 기억이 현재 사용자 말과 충돌하면, 현재 사용자 말이 우선이다.",
            "- 관련 기억은 답변에 자연스럽게 반영하되, 기억 목록을 그대로 읊지 마.",
        ]
        for memory in memories:
            lines.append(f"- {memory}")
        return "\n".join(lines)
