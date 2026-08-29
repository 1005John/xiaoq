"""Local face enrollment and matching for XiaoQ.

The Hailo pipeline produces ArcFace embeddings.  This module deliberately keeps
only normalized feature vectors and enrollment state in a local JSON file so the
mobile API never needs to handle raw biometric data.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_XIAOQ_ROOT = Path(os.environ.get("XIAOQ_ROOT", "/home/johnf/xiaoq"))
DEFAULT_REGISTRY_PATH = DEFAULT_XIAOQ_ROOT / "data" / "face_registry.json"
DEFAULT_AUTH_STATE_PATH = DEFAULT_XIAOQ_ROOT / "data" / "face_auth_state.json"
_NAME_PATTERN = re.compile(r"^[^\\s][^\\r\\n]{0,31}$")


class FaceRegistry:
    """Stores enrolled face centroids and the optional tracking target."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or os.environ.get("XIAOQ_FACE_REGISTRY_PATH", DEFAULT_REGISTRY_PATH))
        self.auth_state_path = Path(os.environ.get("XIAOQ_FACE_AUTH_STATE_PATH", DEFAULT_AUTH_STATE_PATH))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._data = self._load()
        self._enrollment: dict[str, Any] | None = None
        self._last_auth_write_at = 0.0

    def _load(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("people"), list):
                raw.setdefault("version", 1)
                raw.setdefault("active_person_id", None)
                return raw
        except (OSError, json.JSONDecodeError):
            pass
        return {"version": 1, "active_person_id": None, "people": []}

    def _save(self) -> None:
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, self.path)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @staticmethod
    def _normalise(embedding: Any) -> np.ndarray | None:
        try:
            vector = np.asarray(embedding, dtype=np.float32).reshape(-1)
        except (TypeError, ValueError):
            return None
        magnitude = float(np.linalg.norm(vector))
        if vector.size < 64 or not np.isfinite(magnitude) or magnitude < 1e-7:
            return None
        return vector / magnitude

    @staticmethod
    def _public_person(person: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": person.get("id", ""),
            "name": person.get("name", ""),
            "sample_count": int(person.get("sample_count", 0)),
            "created_at": person.get("created_at", ""),
        }

    def _public_enrollment(self) -> dict[str, Any]:
        if not self._enrollment:
            return {"status": "idle"}
        remaining = max(0, int(self._enrollment["deadline"] - time.monotonic()))
        return {
            "status": "collecting",
            "name": self._enrollment["name"],
            "collected": len(self._enrollment["samples"]),
            "required": self._enrollment["required"],
            "remaining_seconds": remaining,
        }

    def _expire_enrollment_locked(self) -> None:
        """Clear a stalled enrollment even when no face embedding arrives."""
        if self._enrollment and time.monotonic() >= self._enrollment["deadline"]:
            self._enrollment = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._expire_enrollment_locked()
            return {
                "people": [self._public_person(person) for person in self._data["people"]],
                "active_person_id": self._data.get("active_person_id"),
                "enrollment": self._public_enrollment(),
            }

    def active_person_id(self) -> str | None:
        with self._lock:
            active = self._data.get("active_person_id")
            return active if isinstance(active, str) and active else None

    def record_authorization(self, person_id: str | None, name: str | None, score: float) -> None:
        """Persist only a short-lived successful match for the active person."""
        now = time.time()
        try:
            minimum_score = float(os.environ.get("XIAOQ_FACE_AUTH_MIN_SCORE", "0.68"))
        except ValueError:
            minimum_score = 0.68
        if score < max(0.0, min(1.0, minimum_score)):
            return
        with self._lock:
            active = self._data.get("active_person_id")
            if not active or person_id != active:
                return
            if now - self._last_auth_write_at < 0.25:
                return
            self._last_auth_write_at = now
        payload = {
            "person_id": str(person_id),
            "name": str(name or ""),
            "score": round(float(score), 4),
            "verified_at": now,
        }
        self.auth_state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.auth_state_path.with_suffix(self.auth_state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, self.auth_state_path)
        try:
            self.auth_state_path.chmod(0o600)
        except OSError:
            pass

    def authorization_status(self, max_age_seconds: float = 2.0) -> dict[str, Any]:
        """Return whether the currently selected identity was just re-verified."""
        with self._lock:
            active = self._data.get("active_person_id")
        if not isinstance(active, str) or not active:
            # "任意人脸跟踪" is an explicit opt-out from identity-gated
            # dialogue. Keep its legacy behavior: no face authorization is
            # required until the app selects a registered person again.
            return {"authorized": True, "reason": "any_face_mode"}
        try:
            state = json.loads(self.auth_state_path.read_text(encoding="utf-8"))
            age = time.time() - float(state.get("verified_at", 0))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return {"authorized": False, "reason": "no_recent_match"}
        authorized = state.get("person_id") == active and 0 <= age <= max_age_seconds
        return {
            "authorized": authorized,
            "reason": "ok" if authorized else "no_recent_match",
            "active_person_id": active,
            "person_name": str(state.get("name") or "") if authorized else "",
            "age_seconds": round(max(0.0, age), 3),
        }

    def start_enrollment(self, name: str, *, required: int = 8, delay_seconds: float = 4.5) -> tuple[bool, str]:
        name = str(name or "").strip()
        if not _NAME_PATTERN.fullmatch(name):
            return False, "姓名需为 1 至 32 个非换行字符"
        with self._lock:
            self._expire_enrollment_locked()
            if self._enrollment:
                return False, "已有注册任务正在进行"
            if any(person.get("name") == name for person in self._data["people"]):
                return False, "该名称已注册，请先删除原有人脸"
            self._enrollment = {
                "name": name,
                "required": max(4, min(16, int(required))),
                "starts_at": time.monotonic() + max(0.0, delay_seconds),
                "deadline": time.monotonic() + max(12.0, delay_seconds + 18.0),
                "samples": [],
                "last_sample_at": 0.0,
            }
        return True, "注册已开始"

    def cancel_enrollment(self) -> None:
        with self._lock:
            self._enrollment = None

    def observe(self, embedding: Any) -> tuple[str | None, str | None, float]:
        """Accept one Hailo embedding and return ``(id, name, score)``."""
        vector = self._normalise(embedding)
        if vector is None:
            return None, None, 0.0
        now = time.monotonic()
        with self._lock:
            enrollment = self._enrollment
            if enrollment:
                if now >= enrollment["deadline"]:
                    self._enrollment = None
                elif now >= enrollment["starts_at"] and now - enrollment["last_sample_at"] >= 0.45:
                    enrollment["samples"].append(vector)
                    enrollment["last_sample_at"] = now
                    if len(enrollment["samples"]) >= enrollment["required"]:
                        centroid = self._normalise(np.mean(enrollment["samples"], axis=0))
                        if centroid is not None:
                            person = {
                                "id": uuid.uuid4().hex,
                                "name": enrollment["name"],
                                "embedding": centroid.astype(float).tolist(),
                                "sample_count": len(enrollment["samples"]),
                                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                            }
                            self._data["people"].append(person)
                            if not self._data.get("active_person_id"):
                                self._data["active_person_id"] = person["id"]
                            self._save()
                        self._enrollment = None

            best_person: dict[str, Any] | None = None
            best_score = -1.0
            for person in self._data["people"]:
                known = self._normalise(person.get("embedding"))
                if known is None or known.shape != vector.shape:
                    continue
                score = float(np.dot(vector, known))
                if score > best_score:
                    best_person, best_score = person, score

            # ArcFace cosine similarity; 0.52 is deliberately conservative
            # for a small, locally enrolled set and can be tuned after testing.
            if best_person is not None and best_score >= 0.52:
                return str(best_person["id"]), str(best_person["name"]), best_score
            return None, None, max(0.0, best_score)

    def select_active(self, person_id: str | None) -> tuple[bool, str]:
        requested = str(person_id or "").strip()
        with self._lock:
            if not requested:
                self._data["active_person_id"] = None
                self._save()
                return True, "已切换为任意人脸跟随"
            if not any(person.get("id") == requested for person in self._data["people"]):
                return False, "未找到已注册的人脸"
            self._data["active_person_id"] = requested
            self._save()
            return True, "已选择跟随目标"

    def delete(self, person_id: str) -> tuple[bool, str]:
        requested = str(person_id or "").strip()
        with self._lock:
            people = self._data["people"]
            kept = [person for person in people if person.get("id") != requested]
            if len(kept) == len(people):
                return False, "未找到已注册的人脸"
            self._data["people"] = kept
            if self._data.get("active_person_id") == requested:
                self._data["active_person_id"] = None
            self._save()
            return True, "已删除人脸"
