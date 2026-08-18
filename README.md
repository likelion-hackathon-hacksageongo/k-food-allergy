# K-Food Allergy Map

알레르기, 식이 제한이 있는 외국인이 자신의 조건에 맞는 한식당과 메뉴를 AI 기반 개인화 지도를 통해 탐색할 수 있도록 돕는 K-food 서비스

## Project Structure

```
dev/
├── frontend/          # React + Vite (JSX, plain CSS)
├── backend/           # Django + DRF + JWT
│   ├── config/        # Django project settings, urls, wsgi
│   ├── accounts/      # Registration, login (JWT auth)
│   ├── profiles/      # Allergy profile (CRUD)
│   ├── restaurants/   # Restaurant data (list, detail)
│   ├── menus/         # Menu items + allergen mapping
│   ├── feedback/      # Post-visit feedback
│   └── analysis/      # AI 분석 API (Django ↔ AI 모듈 브릿지)
└── AI/                # AI 모듈 (OpenAI 기반 분석/문장 생성)
    ├── prompts/       # 시스템 프롬프트
    ├── schemas/       # Pydantic 입출력 스키마
    └── services/      # 분석기, 문장 생성기
```

## Tech Stack

| Layer    | Stack                                         |
|----------|-----------------------------------------------|
| Frontend | React + Vite, React Router, Axios, plain CSS  |
| Backend  | Django 5.1, DRF, SimpleJWT, django-cors-headers |
| Database | SQLite (dev) → PostgreSQL (prod)              |
| AI       | OpenAI GPT-4o-mini, Pydantic, python-dotenv   |

## Getting Started

### Frontend

```bash
cd dev/frontend
npm install
npm run dev          # runs on http://localhost:5173
```

### Backend

```bash
cd backend
py -3.12 -m venv .venv            # Django 5.1 / Pillow don't yet support 3.14 on Windows
source .venv/Scripts/activate    # Windows Git Bash
# source .venv/bin/activate      # Mac/Linux
pip install -r requirements.txt

cp .env.example .env             # local secrets/config, gitignored

python manage.py migrate
python manage.py seed_data       # optional: sample Hongdae restaurants/menus for local dev
python manage.py createsuperuser
python manage.py runserver       # runs on http://localhost:8000
```

**Kakao Local API (restaurant info enrichment, optional):**
1. [developers.kakao.com](https://developers.kakao.com/) → 앱 만들기 → REST API 키 복사
2. `backend/.env`에 `KAKAO_REST_API_KEY=<키>` 추가
3. `python manage.py enrich_restaurants_kakao --dry-run` 으로 확인 후, `--dry-run` 빼고 실제 반영. 전화번호/카테고리/카카오맵 링크를 채워줌 (영업시간은 Kakao API가 제공하지 않아 미포함).

## API Endpoints

| Method | Endpoint                  | Description                  | Auth     | Body / Notes |
|--------|---------------------------|------------------------------|----------|--------------|
| POST   | /api/accounts/register/   | Create new user, returns JWT pair (auto-login) | Public | `{username, email, password, password_confirm}` |
| POST   | /api/accounts/login/      | Get JWT token pair (login with ID, not email) | Public   | `{username, password}` |
| POST   | /api/accounts/token/refresh/ | Refresh access token      | Public   | `{refresh}` |
| GET/PUT| /api/profiles/me/         | Get/update allergy profile   | Required | `{allergens: [...]}` |
| GET    | /api/restaurants/         | List restaurants (paginated) | Required | |
| GET    | /api/restaurants/:id/     | Restaurant detail            | Required | |
| GET    | /api/menus/               | List menus, paginated (?restaurant=id) | Required | |
| GET    | /api/menus/:id/           | Menu item detail (incl. allergens) | Required | |
| GET    | /api/feedback/            | List my feedbacks (paginated) | Required | |
| POST   | /api/feedback/create/     | Submit visit feedback        | Required | |
| POST   | /api/analysis/restaurant/ | Live AI analysis of a restaurant (proxies AI server) | Required | `{restaurant_id}` |
| POST   | /api/analysis/query/      | Generate on-site inquiry phrases (proxies AI server) | Required | `{restaurant_id, menu_item_id?, situations?}` |

List endpoints are paginated with DRF's `PageNumberPagination` (`?page=`, 20 items/page). Every request needs `Authorization: Bearer <access_token>` except the three public ones above.

Menu/restaurant responses include a `personalized` field computed from the logged-in user's allergy profile:
- Menu item: 4-level (`danger` / `warning` / `unconfirmed` / `safe`) + reasons
- Restaurant: 2-level (`safe` / `other`) — `safe` means it has at least one menu item that's safe for this user — plus a `counts` breakdown of its menu items' 4-level verdicts

See [`backend/docs/ai-import-format.md`](backend/docs/ai-import-format.md) for how AI's batch allergen analysis gets imported into the data that powers this.

The `/api/analysis/*` endpoints are separate from the above: they proxy AI's *live* server (port 8100, see `AI/INTEGRATION_GUIDE.md`) for a real-time GPT-based analysis / on-site phrase generation, rather than reading our own precomputed `MenuAllergen` data. Needs `AI_SERVICE_URL` set and the AI server running (`cd AI && uvicorn main:app --reload --port 8100`); returns 503 with a message if it's unreachable.

## Team Roles

- **AI**: Architecture design, model training, allergen analysis logic (`AI/`)
- **Frontend**: React pages and components (`frontend/`)
- **Backend**: API development, data models, admin (`backend/`)
- **Data**: Restaurant/menu data collection, allergen mapping

## Supported Allergens

조사 필요

## Notes

- Frontend communicates with backend via `http://localhost:8000/api/`
- CORS is pre-configured to allow `http://localhost:5173`
- Admin panel: `http://localhost:8000/admin/`
- Swagger UI: `http://localhost:8000/swagger/`
- Analysis results are based on public info and general Korean cooking patterns — never guarantees safety
