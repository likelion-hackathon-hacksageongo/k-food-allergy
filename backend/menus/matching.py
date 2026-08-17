"""
Personalized allergen matching.

This is intentionally NOT an AI call: AI's job (batch) is to populate
`MenuAllergen` rows (and `MenuItem.info_level`) ahead of time. Matching a
specific logged-in user's allergen list against that already-analyzed data
is a cheap, deterministic comparison we do live on every request.

4-level verdict (matches the plan doc's STEP2/3 wording, using the AI
section's shorter labels as the machine-readable keys):
  - danger      "적합 가능성 낮음"   - a matched allergen is confirmed/likely present
  - warning     "일부 확인 필요"     - a matched allergen is only possible/unlikely,
                                       or the underlying menu info is a general pattern
  - unconfirmed "정보 부족"          - not enough info to judge either way
  - safe        "적합 정보 충분"     - no matched allergens, and info is solid
"""

from profiles.models import AllergenChoice
from menus.models import MenuItem, MenuAllergen


class Verdict:
    DANGER = 'danger'
    WARNING = 'warning'
    UNCONFIRMED = 'unconfirmed'
    SAFE = 'safe'

    LABELS = {
        DANGER: '적합 가능성 낮음',
        WARNING: '일부 확인 필요',
        UNCONFIRMED: '정보 부족',
        SAFE: '적합 정보 충분',
    }

    # Best-first, used to pick a restaurant-level headline verdict out of
    # its menu items (i.e. "is there at least one good option here?").
    ORDER_BEST_FIRST = [SAFE, WARNING, UNCONFIRMED, DANGER]


def evaluate_menu_item(menu_item: MenuItem, user_allergens: set[str]) -> dict:
    """
    Compare one menu item's known allergen info against a user's allergen list.

    Returns: {"status": Verdict.*, "label": str, "reasons": [str, ...]}
    """
    allergens = list(menu_item.allergens.all())
    matched = [a for a in allergens if a.allergen_key in user_allergens]

    high_risk = [a for a in matched if a.likelihood in (MenuAllergen.Likelihood.CONFIRMED, MenuAllergen.Likelihood.LIKELY)]
    if high_risk:
        return {
            'status': Verdict.DANGER,
            'label': Verdict.LABELS[Verdict.DANGER],
            'reasons': [_reason(a) for a in high_risk],
        }

    if menu_item.info_level == MenuItem.InfoLevel.INSUFFICIENT:
        return {
            'status': Verdict.UNCONFIRMED,
            'label': Verdict.LABELS[Verdict.UNCONFIRMED],
            'reasons': ['이 메뉴는 아직 확인된 재료 정보가 부족합니다. 현장 문의를 권장합니다.'],
        }

    low_risk = [a for a in matched if a.likelihood in (MenuAllergen.Likelihood.POSSIBLE, MenuAllergen.Likelihood.UNLIKELY)]
    if low_risk or menu_item.info_level == MenuItem.InfoLevel.PATTERN:
        reasons = [_reason(a) for a in low_risk] or [
            '공식 확인 정보가 아닌 일반적인 조리 패턴을 기준으로 한 분석입니다. 현장 확인을 권장합니다.'
        ]
        return {
            'status': Verdict.WARNING,
            'label': Verdict.LABELS[Verdict.WARNING],
            'reasons': reasons,
        }

    return {
        'status': Verdict.SAFE,
        'label': Verdict.LABELS[Verdict.SAFE],
        'reasons': [],
    }


_ALLERGEN_LABELS = dict(AllergenChoice.choices)


def _reason(allergen: MenuAllergen) -> str:
    label = _ALLERGEN_LABELS.get(allergen.allergen_key, allergen.allergen_key)
    text = f"{label} 관련 재료가 {allergen.get_likelihood_display()} 것으로 분석되었습니다."
    if allergen.notes:
        text += f" ({allergen.notes})"
    return text


def evaluate_restaurant(menu_items, user_allergens: set[str]) -> dict:
    """
    Aggregate per-menu-item verdicts into a restaurant-level summary:
    headline verdict = best verdict among its menu items (is there at
    least one option here?), plus a full breakdown count for map/badge UI.
    """
    counts = {Verdict.SAFE: 0, Verdict.WARNING: 0, Verdict.UNCONFIRMED: 0, Verdict.DANGER: 0}
    for item in menu_items:
        result = evaluate_menu_item(item, user_allergens)
        counts[result['status']] += 1

    headline = Verdict.UNCONFIRMED
    for status in Verdict.ORDER_BEST_FIRST:
        if counts[status] > 0:
            headline = status
            break

    return {
        'status': headline,
        'label': Verdict.LABELS[headline],
        'counts': counts,
    }
