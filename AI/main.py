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

from schemas.types import (
    UserAllergyProfile,
    RestaurantInput,
    RestaurantAnalysisResult,
    QueryContext,
    QueryGeneratorResult,
)
from services.analyzer import analyze_restaurant
from services.query_generator import generate_queries


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
