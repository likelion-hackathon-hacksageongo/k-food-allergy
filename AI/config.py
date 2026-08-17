"""
AI 모듈 설정
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# OpenAI 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# 프롬프트 파일 경로
PROMPTS_DIR = BASE_DIR / "prompts"

# 분석 설정
MAX_MENU_ITEMS_PER_REQUEST = 30  # 한 번의 API 호출에 포함할 최대 메뉴 수
TEMPERATURE_ANALYZER = 0.2       # 분석은 일관성 중요 → 낮은 temperature
TEMPERATURE_QUERY_GEN = 0.7      # 문장 생성은 자연스러움 중요 → 약간 높은 temperature

# Rate limit 대응
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "3"))  # 동시 API 호출 수
RETRY_MAX_ATTEMPTS = 3           # 재시도 횟수
RETRY_BASE_DELAY = 5             # 재시도 기본 대기 시간 (초)
