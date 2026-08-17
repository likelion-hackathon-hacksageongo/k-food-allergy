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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from schemas.types import (
    UserAllergyProfile,
    AllergenKey,
    RestaurantInput,
    RestaurantAnalysisResult,
    QueryContext,
    QueryGeneratorResult,
)
from services.analyzer import analyze_restaurant
from services.query_generator import generate_queries
from cache import analysis_cache


app = FastAPI(
    title="K-Food Allergy Map AI",
    description="한식 알레르기 분석 및 현장 문의 문장 생성 API",
    version="0.1.0",
)

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
    """식당 분석 요청: 사용자 알레르겐 + 식당 정보"""
    restaurant: RestaurantInput


class QueryRequest(QueryContext):
    """문의 문장 생성 요청: 알레르겐 + 상황 + 식당/메뉴"""
    pass


class BatchAnalyzeRequest(BaseModel):
    """지도 일괄 분석 요청: 사용자 알레르겐 + 여러 식당"""
    allergens: list[AllergenKey] = Field(
        ...,
        description="사용자가 등록한 알레르겐 목록",
        min_length=1,
    )
    restaurants: list[RestaurantInput] = Field(
        ...,
        description="분석할 식당 목록 (최대 20개)",
        max_length=20,
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
        result = analyze_restaurant(profile, restaurant)
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
        result = generate_queries(context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"문장 생성 중 오류 발생: {str(e)}")

    return result


@app.post("/analyze/batch", response_model=BatchAnalyzeResponse)
def batch_analyze_endpoint(request: BatchAnalyzeRequest):
    """
    여러 식당을 한 번에 분석합니다 (지도 뷰용).

    - 최대 20개 식당
    - 캐시된 결과는 즉시 반환, 미캐시 식당만 API 호출
    - 각 식당의 요약 점수와 판정을 반환 (상세 메뉴 결과는 /analyze에서)
    """
    import concurrent.futures

    profile = UserAllergyProfile(allergens=request.allergens)
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
            result = analyze_restaurant(profile, restaurant)
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
        except Exception:
            return None

    api_call_count = len(to_analyze)

    if to_analyze:
        # 최대 5개 동시 호출 (OpenAI rate limit 고려)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
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
