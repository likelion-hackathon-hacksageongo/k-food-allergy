"""
K-Food Allergy Map — AI 독립 API 서버

FastAPI 기반으로 팀원(FE/BE)이 Django 없이도 AI 기능을 바로 호출할 수 있습니다.

실행:
    cd AI
    source .venv/Scripts/activate
    uvicorn main:app --reload --port 8100

Swagger 문서:
    http://localhost:8100/docs
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from schemas.types import (
    UserAllergyProfile,
    AllergenKey,
    RestaurantInput,
    RestaurantAnalysisResult,
    QueryContext,
    QueryGeneratorResult,
    SupportedLanguage,
)
from services.analyzer import analyze_restaurant
from services.query_generator import generate_queries
from cache import analysis_cache


app = FastAPI(
    title="K-Food Allergy Map AI",
    description="한식 알레르기 분석 및 현장 문의 문장 생성 API",
    version="0.1.0",
)

# 422 에러 시 요청 body 로깅
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = await request.body()
    print(f"\n[422 VALIDATION ERROR] {request.url.path}")
    print(f"[422 BODY] {body[:500]}")
    print(f"[422 ERRORS] {exc.errors()}\n")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

# CORS — FE 개발 서버 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 요청 모델 (FastAPI용 — Pydantic 그대로 사용)
# ============================================================

class AnalyzeRequest(UserAllergyProfile):
    """식당 분석 요청: 사용자 알레르겐 + 식당 정보 + 언어"""
    restaurant: RestaurantInput
    language: str = Field(
        default="ko",
        description="응답 언어 (ko, en, ja, zh, vi, th, es, fr, de, ru, id)",
    )


class QueryRequest(QueryContext):
    """문의 문장 생성 요청: 알레르겐 + 상황 + 식당/메뉴 + 언어"""
    language: str = Field(
        default="ko",
        description="인터페이스 언어 (korean_text는 항상 한국어 유지)",
    )


class BatchAnalyzeRequest(BaseModel):
    """지도 일괄 분석 요청: 사용자 알레르겐 + 여러 식당 + 언어"""
    allergens: list[AllergenKey] = Field(
        default_factory=list,
        description="사용자가 등록한 알레르겐 목록",
    )
    restaurants: list[RestaurantInput] = Field(
        ...,
        description="분석할 식당 목록 (최대 20개)",
        max_length=20,
    )
    language: str = Field(
        default="ko",
        description="응답 언어 (ko, en, ja, zh, vi, th, es, fr)",
    )


class RestaurantSummary(BaseModel):
    """식당 요약 (지도 뷰용 — 경량)"""
    restaurant_id: int
    restaurant_name: str
    overall_score: int
    overall_suitability: str
    safe_menu_count: int
    caution_menu_count: int
    avoid_menu_count: int
    risk_summary: str


class BatchAnalyzeResponse(BaseModel):
    """일괄 분석 응답"""
    results: list[RestaurantSummary]
    cached_count: int = Field(description="캐시에서 반환된 식당 수")
    api_call_count: int = Field(description="새로 API 호출한 식당 수")


# ============================================================
# 엔드포인트
# ============================================================

@app.get("/health")
def health_check():
    """서버 상태 확인"""
    return {"status": "ok", "service": "k-food-allergy-ai"}


@app.post("/analyze", response_model=RestaurantAnalysisResult)
def analyze_restaurant_endpoint(request: AnalyzeRequest):
    """
    식당 전체 메뉴를 사용자 알레르기 프로필 기준으로 분석합니다.

    - 메뉴별 적합도 (safe / caution / avoid / unknown)
    - 식당 전체 점수 (0~100)
    - 숨은 알레르겐 및 교차오염 정보
    """
    profile = UserAllergyProfile(allergens=request.allergens)
    restaurant = request.restaurant

    if not restaurant.menu_items:
        raise HTTPException(status_code=400, detail="메뉴가 비어있습니다.")

    try:
        result = analyze_restaurant(profile, restaurant, language=request.language)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {str(e)}")

    return result


@app.post("/query", response_model=QueryGeneratorResult)
def generate_query_endpoint(request: QueryRequest):
    """
    사용자의 알레르기 정보와 상황에 맞는 한국어 문의 문장을 생성합니다.

    상황 코드:
    - ingredient_check: 재료 확인
    - broth_sauce: 육수·소스 문의
    - cross_contamination: 교차오염 문의
    - modification: 재료 변경 요청
    """
    context = QueryContext(
        allergens=request.allergens,
        restaurant_name=request.restaurant_name,
        menu_name=request.menu_name,
        situations=request.situations,
    )

    try:
        result = generate_queries(context, language=request.language)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"문장 생성 중 오류 발생: {str(e)}")

    return result


@app.post("/debug/batch")
async def debug_batch(request: Request):
    """디버그: BE가 보내는 raw body 확인"""
    body = await request.json()
    print(f"[DEBUG /analyze/batch] keys: {list(body.keys())}")
    print(f"[DEBUG] allergens: {body.get('allergens')}")
    print(f"[DEBUG] language: {body.get('language')}")
    restaurants = body.get('restaurants', [])
    print(f"[DEBUG] restaurant count: {len(restaurants)}")
    if restaurants:
        first = restaurants[0]
        print(f"[DEBUG] first restaurant keys: {list(first.keys())}")
        print(f"[DEBUG] first restaurant: id={first.get('id')}, name={first.get('name')}, menu_items={len(first.get('menu_items', []))}")
        if first.get('menu_items'):
            print(f"[DEBUG] first menu item: {first['menu_items'][0]}")
    return {"received": True, "restaurant_count": len(restaurants), "allergens": body.get("allergens")}


@app.post("/analyze/batch", response_model=BatchAnalyzeResponse)
def batch_analyze_endpoint(request: BatchAnalyzeRequest):
    """
    여러 식당을 한 번에 분석합니다 (지도 뷰용).

    - 최대 20개 식당
    - 캐시된 결과는 즉시 반환, 미캐시 식당만 API 호출
    - 각 식당의 요약 점수와 판정을 반환 (상세 메뉴 결과는 /analyze에서)
    """
    import concurrent.futures

    if not request.allergens:
        # 알레르겐 없음 = 모든 메뉴 안전
        results = []
        for restaurant in request.restaurants:
            if not restaurant.menu_items:
                continue
            results.append(RestaurantSummary(
                restaurant_id=restaurant.id,
                restaurant_name=restaurant.name,
                overall_score=100,
                overall_suitability="safe",
                safe_menu_count=len(restaurant.menu_items),
                caution_menu_count=0,
                avoid_menu_count=0,
                risk_summary="No allergens registered. All menus are available.",
            ))
        return BatchAnalyzeResponse(results=results, cached_count=0, api_call_count=0)

    profile = UserAllergyProfile(allergens=request.allergens)
    language = request.language
    results = []
    cached_count = 0
    to_analyze = []

    # 1단계: 캐시 확인 — 캐시된 건 바로 수집, 아닌 건 분석 대기열에
    for restaurant in request.restaurants:
        if not restaurant.menu_items:
            continue

        cache_data = {
            "allergens": sorted(a.value for a in profile.allergens),
            "restaurant_id": restaurant.id,
            "menu_ids": sorted(m.id for m in restaurant.menu_items),
            "language": language,
        }
        cached = analysis_cache.get("analyze", cache_data)

        if cached:
            results.append(RestaurantSummary(
                restaurant_id=cached["restaurant_id"],
                restaurant_name=cached["restaurant_name"],
                overall_score=cached["overall_score"],
                overall_suitability=cached["overall_suitability"],
                safe_menu_count=cached["safe_menu_count"],
                caution_menu_count=cached["caution_menu_count"],
                avoid_menu_count=cached["avoid_menu_count"],
                risk_summary=cached["risk_summary"],
            ))
            cached_count += 1
        else:
            to_analyze.append(restaurant)

    # 2단계: 미캐시 식당 병렬 분석
    def _analyze_one(restaurant: RestaurantInput) -> RestaurantSummary | None:
        try:
            result = analyze_restaurant(profile, restaurant, language=language)
            return RestaurantSummary(
                restaurant_id=result.restaurant_id,
                restaurant_name=result.restaurant_name,
                overall_score=result.overall_score,
                overall_suitability=result.overall_suitability.value,
                safe_menu_count=result.safe_menu_count,
                caution_menu_count=result.caution_menu_count,
                avoid_menu_count=result.avoid_menu_count,
                risk_summary=result.risk_summary,
            )
        except Exception as e:
            import traceback
            print(f"[BATCH ERROR] {restaurant.name}: {e}")
            traceback.print_exc()
            return None

    api_call_count = len(to_analyze)

    if to_analyze:
        # 최대 3개 동시 호출 (OpenAI rate limit 고려)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(_analyze_one, r): r for r in to_analyze}
            for future in concurrent.futures.as_completed(futures):
                summary = future.result()
                if summary:
                    results.append(summary)

    # 점수 높은 순 정렬
    results.sort(key=lambda r: r.overall_score, reverse=True)

    return BatchAnalyzeResponse(
        results=results,
        cached_count=cached_count,
        api_call_count=api_call_count,
    )


@app.get("/cache/stats")
def cache_stats():
    """캐시 상태 확인 (디버그용)"""
    from cache import query_cache
    return {
        "analysis_cache": analysis_cache.stats(),
        "query_cache": query_cache.stats(),
    }


@app.post("/cache/clear")
def cache_clear():
    """캐시 초기화 (디버그용)"""
    from cache import query_cache
    analysis_cache.clear()
    query_cache.clear()
    return {"status": "cleared"}


# ============================================================
# 메뉴판 스캔 엔드포인트
# ============================================================

from fastapi import File, UploadFile, Form
from typing import Optional
from schemas.types import MenuScanResult
from services.menu_scanner import scan_menu


@app.post("/scan", response_model=MenuScanResult)
async def scan_menu_endpoint(
    image: UploadFile = File(..., description="메뉴판 사진 (jpg, png, webp)"),
    allergens: str = Form(default="", description="쉼표 구분 알레르겐 코드 (예: soy,shellfish,wheat)"),
    language: str = Form(default="en", description="번역 대상 언어 코드"),
):
    """
    메뉴판 사진을 스캔하여 번역 + 알레르겐 체크 결과를 반환합니다.

    - 이미지에서 메뉴 항목을 자동 인식
    - 사용자가 설정한 언어로 메뉴명과 설명을 번역
    - 사용자 알레르겐과 매칭하여 위험도 표시

    지원 이미지 형식: JPEG, PNG, WebP, GIF
    """
    # 이미지 읽기
    image_bytes = await image.read()

    if not image_bytes:
        raise HTTPException(status_code=400, detail="이미지 파일이 비어있습니다.")

    # 파일 확장자에서 형식 추출
    filename = image.filename or "image.jpeg"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpeg"
    format_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "gif": "gif"}
    image_format = format_map.get(ext, "jpeg")

    # 알레르겐 파싱 (쉼표 구분 문자열 → 리스트)
    allergen_list = [a.strip() for a in allergens.split(",") if a.strip()] if allergens else []

    try:
        result = scan_menu(
            image_bytes=image_bytes,
            allergens=allergen_list,
            language=language,
            image_format=image_format,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"메뉴 스캔 중 오류 발생: {str(e)}")

    return result


# ============================================================
# 사전 분석 (Pre-computed) 엔드포인트
# ============================================================


class PrecomputeRequest(BaseModel):
    """사전 분석 트리거 요청"""
    user_id: str = Field(..., description="사용자 식별자")
    allergens: list[AllergenKey] = Field(..., description="사용자 알레르겐 목록", min_length=1)
    restaurants: list[RestaurantInput] = Field(..., description="분석할 식당 목록")
    language: str = Field(default="ko", description="응답 언어")


class PrecomputeSingleRequest(BaseModel):
    """단일 식당 재분석 요청 (메뉴 변경 시)"""
    user_id: str = Field(..., description="사용자 식별자")
    allergens: list[AllergenKey] = Field(..., description="사용자 알레르겐 목록", min_length=1)
    restaurant: RestaurantInput = Field(..., description="재분석할 식당")
    language: str = Field(default="ko", description="응답 언어")


class ScoresResponse(BaseModel):
    """지도 뷰용 즉시 응답"""
    user_id: str
    computed_at: str | None = None
    restaurants: dict[str, RestaurantSummary] = Field(default_factory=dict)


@app.get("/scores/{user_id}", response_model=ScoresResponse)
def get_scores(user_id: str):
    """
    사전 분석된 식당 점수를 즉시 반환합니다 (지도 뷰용).

    - 응답 시간: <10ms (파일에서 읽기만)
    - 사전 분석이 안 되어 있으면 빈 결과 반환
    - FE는 이 엔드포인트로 지도 핀에 점수를 표시
    """
    from store import get_user_scores

    data = get_user_scores(user_id)

    if not data:
        return ScoresResponse(user_id=user_id, computed_at=None, restaurants={})

    # dict → RestaurantSummary 변환
    restaurants = {}
    for rid, summary in data.get("restaurants", {}).items():
        restaurants[rid] = RestaurantSummary(**summary)

    return ScoresResponse(
        user_id=user_id,
        computed_at=data.get("computed_at"),
        restaurants=restaurants,
    )


@app.post("/precompute/trigger")
def trigger_precompute(request: PrecomputeRequest):
    """
    사전 분석을 트리거합니다 (백그라운드 실행).

    BE가 호출하는 시점:
    - 사용자가 알레르기 프로필을 등록/변경했을 때
    - 새 사용자가 회원가입 후 프로필을 완성했을 때

    모든 식당에 대해 병렬 분석 후 결과를 저장합니다.
    """
    import threading
    from precompute import precompute_for_user

    allergens = [a.value for a in request.allergens]
    restaurants = [r.model_dump() for r in request.restaurants]

    # 백그라운드 스레드에서 실행 (요청 즉시 응답)
    def _run():
        precompute_for_user(
            user_id=request.user_id,
            allergens=allergens,
            restaurants=restaurants,
            language=request.language,
        )

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {
        "status": "started",
        "user_id": request.user_id,
        "restaurant_count": len(request.restaurants),
        "message": "백그라운드에서 분석이 진행됩니다. GET /scores/{user_id}로 결과를 확인하세요.",
    }


@app.post("/precompute/restaurant")
def trigger_restaurant_recompute(request: PrecomputeSingleRequest):
    """
    단일 식당 재분석을 트리거합니다.

    BE가 호출하는 시점:
    - 식당 메뉴가 추가/변경/삭제되었을 때
    - 데이터팀이 식당 정보를 업데이트했을 때
    """
    import threading
    from precompute import precompute_single_restaurant

    allergens = [a.value for a in request.allergens]
    restaurant = request.restaurant.model_dump()

    def _run():
        precompute_single_restaurant(
            user_id=request.user_id,
            allergens=allergens,
            restaurant=restaurant,
            language=request.language,
        )

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {
        "status": "started",
        "user_id": request.user_id,
        "restaurant_id": request.restaurant.id,
        "message": "해당 식당 재분석이 진행됩니다.",
    }
