"""
Personalized allergen matching.

This is intentionally NOT an AI call: AI's job (batch) is to populate
`MenuAllergen` rows (and `MenuItem.info_level`) ahead of time. Matching a
specific logged-in user's allergen list against that already-analyzed data
is a cheap, deterministic comparison we do live on every request.

MenuAllergen.likelihood is one of confirmed / likely / possible / none
(Data team's classification scale):
  - confirmed  들어감이 확실함
  - likely     들어갔을 수 있으니 확인 필요
  - possible   알 수 없음
  - none       들어가지 않을 확률이 높음
`none` carries no risk in the matching below (same as if no row existed).

Per-menu-item verdict (4-level, matches the plan doc's STEP2/3 wording,
using the AI section's shorter labels as the machine-readable keys):
  - danger      "적합 가능성 낮음"   - a matched allergen is confirmed/likely present
  - warning     "일부 확인 필요"     - a matched allergen is only possible,
                                       or the underlying menu info is a general pattern
  - unconfirmed "정보 부족"          - not enough info to judge either way
  - safe        "적합 정보 충분"     - no matched allergens, and info is solid

Per-restaurant verdict (2-level, simpler than the menu-item one): a
restaurant is "safe" if it has at least one menu item that's safe for
this user, otherwise "other" (needs a closer look at the menu detail).
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

    low_risk = [a for a in matched if a.likelihood == MenuAllergen.Likelihood.POSSIBLE]
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

# Human-facing phrasing for each likelihood tier, per the Data team's
# definitions (see module docstring). Kept separate from the model's
# `choices` labels so this can read naturally in a Korean sentence.
_LIKELIHOOD_PHRASES = {
    MenuAllergen.Likelihood.CONFIRMED: '들어있는 것으로 확인',
    MenuAllergen.Likelihood.LIKELY: '들어갔을 수 있어 확인이 필요한 것으로 분석',
    MenuAllergen.Likelihood.POSSIBLE: '포함 여부를 알 수 없는 것으로 분석',
}


def _reason(allergen: MenuAllergen) -> str:
    label = _ALLERGEN_LABELS.get(allergen.allergen_key, allergen.allergen_key)
    phrase = _LIKELIHOOD_PHRASES.get(allergen.likelihood, allergen.get_likelihood_display())
    text = f"{label} 관련 재료가 {phrase}되었습니다."
    if allergen.notes:
        text += f" ({allergen.notes})"
    return text


# Restaurant-level verdict is intentionally simpler than the menu-item one:
# "safe" (there's at least one menu item confirmed safe for this user) vs
# "other" (everything else - needs a closer look at the menu detail).
RESTAURANT_SAFE = 'safe'
RESTAURANT_OTHER = 'other'
RESTAURANT_LABELS = {
    RESTAURANT_SAFE: '확실히 안전',
    RESTAURANT_OTHER: '확인 필요',
}


def evaluate_restaurant(menu_items, user_allergens: set[str]) -> dict:
    """
    Aggregate per-menu-item verdicts into a restaurant-level summary:
    binary status (is there at least one safe option here?) plus the
    full safe/warning/unconfirmed/danger breakdown for the detail page.
    """
    counts = {Verdict.SAFE: 0, Verdict.WARNING: 0, Verdict.UNCONFIRMED: 0, Verdict.DANGER: 0}
    for item in menu_items:
        result = evaluate_menu_item(item, user_allergens)
        counts[result['status']] += 1

    status = RESTAURANT_SAFE if counts[Verdict.SAFE] > 0 else RESTAURANT_OTHER

    return {
        'status': status,
        'label': RESTAURANT_LABELS[status],
        'counts': counts,
    }
