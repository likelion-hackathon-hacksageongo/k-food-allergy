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
cd dev/backend
python -m venv .venv
source .venv/Scripts/activate    # Windows Git Bash
# source .venv/bin/activate      # Mac/Linux
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver       # runs on http://localhost:8000
```

## API Endpoints

| Method | Endpoint                  | Description                  | Auth     |
|--------|---------------------------|------------------------------|----------|
| POST   | /api/accounts/register/   | Create new user              | Public   |
| POST   | /api/accounts/login/      | Get JWT token pair           | Public   |
| POST   | /api/accounts/token/refresh/ | Refresh access token      | Public   |
| GET/PUT| /api/profiles/me/         | Get/update allergy profile   | Required |
| GET    | /api/restaurants/         | List restaurants             | Required |
| GET    | /api/restaurants/:id/     | Restaurant detail            | Required |
| GET    | /api/menus/               | List menus (?restaurant=id)  | Required |
| GET    | /api/menus/:id/           | Menu item detail             | Required |
| GET    | /api/feedback/            | List my feedbacks            | Required |
| POST   | /api/feedback/create/     | Submit visit feedback        | Required |
| POST   | /api/analysis/restaurant/ | AI 식당 전체 분석            | Required |
| POST   | /api/analysis/query/      | 현장 문의 한국어 문장 생성    | Required |
| POST   | /api/analysis/batch/      | 지도 다중 식당 요약 분석      | Required |

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
