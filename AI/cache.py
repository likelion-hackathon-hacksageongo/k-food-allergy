"""
인메모리 캐시 레이어

동일한 (알레르겐 조합 + 식당 메뉴) 요청에 대해 OpenAI 호출을 생략합니다.
TTL 기반으로 일정 시간 후 자동 만료됩니다.

프로덕션에서는 Redis로 교체 가능하지만, 해커톤/MVP 단계에서는 인메모리로 충분합니다.
"""

import hashlib
import json
import time
from typing import Any


class TTLCache:
    """간단한 TTL 기반 인메모리 캐시"""

    def __init__(self, default_ttl: int = 3600):
        """
        Args:
            default_ttl: 기본 캐시 만료 시간 (초). 기본 1시간.
        """
        self._store: dict[str, tuple[Any, float]] = {}
        self._default_ttl = default_ttl

    def _make_key(self, prefix: str, data: dict) -> str:
        """데이터를 정규화하여 해시 키 생성"""
        normalized = json.dumps(data, sort_keys=True, ensure_ascii=False)
        hashed = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        return f"{prefix}:{hashed}"

    def get(self, prefix: str, data: dict) -> Any | None:
        """캐시 조회. 만료되었으면 None 반환."""
        key = self._make_key(prefix, data)
        if key not in self._store:
            return None

        value, expires_at = self._store[key]
        if time.time() > expires_at:
            del self._store[key]
            return None

        return value

    def set(self, prefix: str, data: dict, value: Any, ttl: int = None):
        """캐시 저장."""
        key = self._make_key(prefix, data)
        expires_at = time.time() + (ttl or self._default_ttl)
        self._store[key] = (value, expires_at)

    def clear(self):
        """전체 캐시 초기화"""
        self._store.clear()

    def stats(self) -> dict:
        """캐시 통계"""
        now = time.time()
        total = len(self._store)
        alive = sum(1 for _, (_, exp) in self._store.items() if exp > now)
        return {"total_entries": total, "alive": alive, "expired": total - alive}


# 싱글톤 캐시 인스턴스
# 분석 결과: 6시간 캐시 (식당 메뉴는 자주 안 바뀜)
analysis_cache = TTLCache(default_ttl=6 * 3600)

# 문장 생성: 1시간 캐시 (같은 조건이면 동일 문장 제공)
query_cache = TTLCache(default_ttl=1 * 3600)
