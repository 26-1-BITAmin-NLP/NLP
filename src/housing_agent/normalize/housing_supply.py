# 주택 공급 데이터 정규화 코드
from __future__ import annotations
from typing import Any, Dict

from src.housing_agent.normalize.common import (
    make_seq_id,
    extract_age_range,
    extract_income_max,
    detect_no_house,
    extract_regions,
)

# main normalize function
def normalize_housing_supply(item: Dict[str, Any], seq_idx: int | None = None) -> Dict[str, Any]:

    policy_id = make_seq_id("SUP", seq_idx) if seq_idx is not None else str(item["policy_id"]).strip()
    title = (item.get("title") or "").strip()

    target_text = (item.get("target_text") or "").strip()
    condition_text = (item.get("condition_text") or "").strip()
    benefit_text = (item.get("benefit_text") or "").strip()
    apply_text = (item.get("apply_text") or "").strip()
    contact_text = (item.get("contact_text") or "").strip()

    eligibility_text = "\n".join([t for t in [target_text, condition_text] if t]).strip() or None
    process_text = "\n".join([t for t in [apply_text, contact_text] if t]).strip() or None
    benefit_text = benefit_text or None

    # region 힌트를 같이 넣어서 지역 추출 보강
    region_hint = (item.get("region") or "")
    regions = extract_regions(region_hint + "\n" + (eligibility_text or ""))

    age_min, age_max = extract_age_range(eligibility_text or "")
    income_max_m = extract_income_max(eligibility_text or "")
    requires_no_house = detect_no_house(eligibility_text or "")

    eligibility_struct = {
        "age_min": age_min,
        "age_max": age_max,
        "income_max_m": income_max_m,
        "asset_max_m": None,
        "household_types": [],
        "requires_no_house": requires_no_house,
        "regions": regions,
        "housing_types": [],
    }

    return {
        "policy_id": policy_id,
        "category": "housing_supply",
        "title": title,

        "eligibility_struct": eligibility_struct,

        "eligibility_text": eligibility_text,
        "benefit_text": benefit_text,
        "process_text": process_text,

        "provider": item.get("provider"),
        "region": item.get("region"),
        "source_url": item.get("source_url"),
    }
