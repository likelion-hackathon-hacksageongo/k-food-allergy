"""
AI 모듈 입출력 스키마 정의

분석기(Analyzer)와 문장 생성기(Query Generator)에서 사용하는
요청/응답 데이터 모델을 정의합니다.
"""

from enum import Enum
from pydantic import BaseModel, Field


# ============================================================
# 공통 타입
# ============================================================

class AllergenKey(str, Enum):
    """지원 알레르겐 목록 (16종)"""
    SHELLFISH = "shellfish"      # 갑각류 (새우, 게, 랍스터)
    NUTS = "nuts"                # 견과류 (호두, 아몬드, 잣)
    WHEAT = "wheat"              # 밀·글루텐
    SOY = "soy"                  # 대두 (두부, 된장, 간장)
    EGG = "egg"                  # 달걀
    DAIRY = "dairy"              # 유제품 (우유, 치즈, 버터)
    FISH = "fish"                # 생선·어류 (멸치, 고등어)
    MOLLUSK = "mollusk"          # 조개류 (전복, 오징어, 조개)
    PEACH = "peach"              # 복숭아
    PEANUT = "peanut"            # 땅콩
    PORK = "pork"                # 돼지고기
    BEEF = "beef"                # 쇠고기
    CHICKEN = "chicken"          # 닭고기
    SULFITES = "sulfites"        # 아황산류 (와인, 식초)
    BUCKWHEAT = "buckwheat"      # 메밀
    TOMATO = "tomato"            # 토마토


class Likelihood(str, Enum):
    """알레르겐 포함 가능성 수준"""
    CONFIRMED = "confirmed"      # 확인됨 (주재료로 포함, 90% 이상)
    LIKELY = "likely"            # 포함 가능성 있음 (확인 필요, 70-80%)
    POSSIBLE = "possible"        # 포함 여부 알 수 없음 (확인 필요, 20-30%)
    NONE = "none"                # 포함되지 않을 확률이 높음


class InfoLevel(str, Enum):
    """정보 충분도"""
    CONFIRMED = "confirmed"      # 공개 메뉴판 등 확인된 정보 기반
    PATTERN = "pattern"          # 일반 조리 패턴 기반 추정
    INSUFFICIENT = "insufficient"  # 정보 부족 (확인 필요)


class SuitabilityLevel(str, Enum):
    """적합 가능성 등급"""
    SAFE = "safe"                # 적합 가능 (확인된 안전 메뉴)
    CAUTION = "caution"          # 주의 필요 (확인 필요 항목 있음)
    AVOID = "avoid"              # 회피 권장 (알레르겐 포함 확인)
    UNKNOWN = "unknown"          # 판단 불가 (정보 부족)


class SupportedLanguage(str, Enum):
    """지원 언어 목록"""
    KO = "ko"    # 한국어
    EN = "en"    # English
    JA = "ja"    # 日本語
    ZH = "zh"    # 中文
    VI = "vi"    # Tiếng Việt
    TH = "th"    # ภาษาไทย
    ES = "es"    # Español
    FR = "fr"    # Français
    DE = "de"    # Deutsch
    RU = "ru"    # Русский
    ID = "id"    # Bahasa Indonesia


# 언어 코드 → 자연어 이름 매핑 (프롬프트용)
LANGUAGE_NAMES = {
    "ko": "한국어",
    "en": "English",
    "ja": "日本語 (Japanese)",
    "zh": "中文 (Chinese)",
    "vi": "Tiếng Việt (Vietnamese)",
    "th": "ภาษาไทย (Thai)",
    "es": "Español (Spanish)",
    "fr": "Français (French)",
    "de": "Deutsch (German)",
    "ru": "Русский (Russian)",
    "id": "Bahasa Indonesia (Indonesian)",
}


# ============================================================
# 분석기 (Analyzer) 입력
# ============================================================

class UserAllergyProfile(BaseModel):
    """사용자 알레르기 프로필"""
    allergens: list[AllergenKey] = Field(
        ...,
        description="사용자가 등록한 알레르겐 목록",
        min_length=1,
    )


class MenuItemInput(BaseModel):
    """분석 대상 메뉴 항목"""
    id: int = Field(..., description="메뉴 항목 DB ID")
    name: str = Field(..., description="메뉴명 (한국어)")
    description: str = Field(default="", description="메뉴 설명")
    ingredients: list[str] = Field(default_factory=list, description="알려진 재료 목록")


class RestaurantInput(BaseModel):
    """분석 대상 식당 정보"""
    id: int = Field(..., description="식당 DB ID")
    name: str = Field(..., description="식당명 (한국어)")
    category: str = Field(default="한식", description="음식 카테고리")
    menu_items: list[MenuItemInput] = Field(
        default_factory=list,
        description="해당 식당의 전체 메뉴 목록",
    )


# ============================================================
# 분석기 (Analyzer) 출력
# ============================================================

class AllergenDetail(BaseModel):
    """개별 알레르겐 분석 상세"""
    allergen: AllergenKey
    likelihood: Likelihood
    source: str = Field(..., description="판단 근거 (예: '된장은 대두 유래 재료')")
    hidden_risk: str = Field(default="", description="숨은 위험 요소 설명")


class MenuAnalysisResult(BaseModel):
    """단일 메뉴 분석 결과"""
    menu_id: int
    menu_name: str
    suitability: SuitabilityLevel
    info_level: InfoLevel
    allergen_details: list[AllergenDetail] = Field(
        default_factory=list,
        description="해당 메뉴에서 발견된 알레르겐 상세 목록",
    )
    check_items: list[str] = Field(
        default_factory=list,
        description="현장에서 확인해야 할 항목 목록",
    )
    summary: str = Field(..., description="메뉴 적합성 요약 (1~2문장)")


class RestaurantAnalysisResult(BaseModel):
    """식당 전체 분석 결과"""
    restaurant_id: int
    restaurant_name: str
    overall_score: int = Field(
        ...,
        ge=0, le=100,
        description="식당 전체 적합도 점수 (0: 매우 위험 ~ 100: 매우 안전)",
    )
    overall_suitability: SuitabilityLevel
    safe_menu_count: int = Field(..., description="적합 가능 메뉴 수")
    caution_menu_count: int = Field(..., description="주의 필요 메뉴 수")
    avoid_menu_count: int = Field(..., description="회피 권장 메뉴 수")
    risk_summary: str = Field(
        ...,
        description="식당 전반의 위험 요약 (예: '대두 기반 양념 다수 사용')",
    )
    cross_contamination_notes: str = Field(
        default="",
        description="교차오염 관련 참고사항",
    )
    menu_results: list[MenuAnalysisResult] = Field(
        ...,
        description="개별 메뉴 분석 결과 목록",
    )


# ============================================================
# 문장 생성기 (Query Generator) 입력
# ============================================================

class QueryContext(BaseModel):
    """문의 문장 생성 요청 컨텍스트"""
    allergens: list[AllergenKey] = Field(
        ...,
        description="사용자의 알레르겐 목록",
        min_length=1,
    )
    restaurant_name: str = Field(default="", description="식당명 (선택)")
    menu_name: str = Field(default="", description="특정 메뉴명 (선택)")
    situations: list[str] = Field(
        default_factory=lambda: ["ingredient_check"],
        description="문의 상황 목록: ingredient_check, broth_sauce, cross_contamination, modification",
    )


# ============================================================
# 문장 생성기 (Query Generator) 출력
# ============================================================

class GeneratedQuery(BaseModel):
    """생성된 개별 문의 문장"""
    situation: str = Field(..., description="문의 상황 (예: 'ingredient_check')")
    situation_label: str = Field(..., description="상황 한국어 라벨 (예: '재료 확인')")
    korean_text: str = Field(..., description="생성된 한국어 문의 문장")
    english_note: str = Field(
        default="",
        description="문장의 영어 설명 (외국인 사용자 참고용)",
    )


class QueryGeneratorResult(BaseModel):
    """문장 생성 전체 결과"""
    intro_text: str = Field(
        ...,
        description="종합 소개 문장 (예: '저는 OO에 알레르기가 있습니다')",
    )
    queries: list[GeneratedQuery] = Field(
        ...,
        description="상황별 생성된 문의 문장 목록",
    )
    disclaimer: str = Field(
        default="이 문장은 직원과의 의사소통을 돕기 위한 참고 자료입니다. 실제 조리 환경을 보증하지 않습니다.",
        description="면책 안내 문구",
    )
