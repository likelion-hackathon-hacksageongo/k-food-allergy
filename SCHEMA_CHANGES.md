# 스키마 통일 변경사항 (팀 공유용)

AI/BE/FE/데이터 간 데이터 구조가 불일치했던 부분을 정리하고 수정했습니다.

---

## 1. Likelihood (알레르겐 포함 가능성) — AI 수정 완료, BE 수정 필요

메뉴별 알레르겐이 얼마나 포함되어 있는지를 나타내는 값.

| 값 | 의미 | 사용자에게 표시 |
|----|------|---------------|
| `confirmed` | 90% 이상 포함 확인 | 🔴 포함 확인됨 |
| `likely` | 70-80% 포함 가능성 | 🟡 확인 필요 |
| `possible` | 20-30% 포함 가능성 | 🟡 확인 필요 |
| `none` | 포함되지 않을 확률 높음 | 표시 없음 |

**변경 내용:**
- AI: `unlikely` → `none` 으로 변경 ✅ 완료
- BE: `matching.py`에서 `likely`를 danger → warning으로 이동 필요

```python
# BE 변경 필요 (backend/menus/matching.py)
# 변경 전
high_risk = [a for a in matched if a.likelihood in (CONFIRMED, LIKELY)]
# 변경 후
high_risk = [a for a in matched if a.likelihood == CONFIRMED]

# 변경 전
low_risk = [a for a in matched if a.likelihood == POSSIBLE]
# 변경 후
low_risk = [a for a in matched if a.likelihood in (LIKELY, POSSIBLE)]
```

---

## 2. InfoLevel (정보 충분도) — AI 수정 완료

분석 결과가 얼마나 신뢰할 수 있는지를 나타내는 값.

| 값 | 의미 |
|----|------|
| `confirmed` | 공개 메뉴판 등 확인된 정보 기반 |
| `pattern` | 일반 조리 패턴으로 추정 |
| `insufficient` | 정보 부족, 현장 확인 필요 |

**변경 내용:**
- AI 이전 값: `sufficient` / `moderate` / `insufficient`
- AI 변경 후: `confirmed` / `pattern` / `insufficient` (BE와 동일)

---

## 3. name 필드 — AI/데이터 수정 완료

식당과 메뉴에 영어 이름(`name`)과 한국어 이름(`name_ko`)을 분리.

**변경 전:**
```json
{ "name": "홍대 한솥밥" }
```

**변경 후:**
```json
{ "name": "Hongdae Hansotbap", "name_ko": "홍대 한솥밥" }
```

**데이터팀:** 수집 시 영어 이름 + 한국어 이름 둘 다 기입 부탁드립니다.
**BE:** import 시 `name_ko`로 매칭하도록 변경 필요.

---

## 4. 언어 코드 — AI 수정 완료

사용자 언어 설정에 3개 추가됨:

| 추가 | 언어 |
|------|------|
| `de` | Deutsch (독일어) |
| `ru` | Русский (러시아어) |
| `id` | Bahasa Indonesia (인도네시아어) |

전체 지원: `ko, en, ja, zh, vi, th, es, fr, de, ru, id`

---

## 5. 지도 뷰 표시 기준 (합의 사항)

- **식당**: `overall_score` 기준으로 초록(갈 수 있음) / 회색(나머지)
- **메뉴**: 위의 likelihood 기준으로 🔴/🟡/표시없음

FE에서 임계값 결정 필요 (제안: score >= 60 → 초록)

---

## 6. FE API 경로 — FE/BE 협의 필요

현재 FE가 호출 중인 `POST /api/ai/menu-recommendations`는 BE에 존재하지 않음.

**방향:** BE가 AI 서버(localhost:8100)를 내부 호출하는 엔드포인트를 생성.
자세한 연동 방법은 `AI/INTEGRATION_GUIDE.md` 참고.

---

## 담당자별 TODO

| 담당 | 할 일 | 상태 |
|------|------|------|
| AI | Likelihood `unlikely`→`none` | ✅ 완료 |
| AI | InfoLevel `sufficient`→`confirmed`, `moderate`→`pattern` | ✅ 완료 |
| AI | 언어 코드 de/ru/id 추가 | ✅ 완료 |
| AI | DATA_FORMAT에 name_ko 추가 | ✅ 완료 |
| **BE** | matching.py에서 likely를 warning으로 이동 | ⬜ 미완 |
| **BE** | import 커맨드 name_ko 매칭 | ⬜ 미완 |
| **FE** | API 경로를 실제 BE 엔드포인트로 변경 | ⬜ 미완 |
| **데이터** | 수집 시 name + name_ko 둘 다 기입 | ⬜ 미완 |
