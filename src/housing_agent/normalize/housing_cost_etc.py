# 주거비/기타 지원 데이터 정규화 코드
from __future__ import annotations
from typing import Any, Dict, List

from src.housing_agent.normalize.common import (
    make_seq_id,
    norm_keep_lines,
    dedup_texts,
    join_lines,
    extract_age_range,
    extract_income_max,
    detect_no_house,
    extract_regions,
)

# table을 line으로 변환
def table_to_lines(tb: Dict[str, Any]) -> List[str]:
    headers = tb.get("headers") or []
    rows = tb.get("rows") or []
    lines: List[str] = []
    if headers:
        lines.append(" | ".join([str(x) for x in headers]))
    for r in rows:
        lines.append(" | ".join([str(x) for x in r]))
    return lines

# sections title, texts 매핑
def section_map(title: str) -> str:
    t = norm_keep_lines(title).replace("\n", " ")

    if any(k in t for k in ["지원대상", "대상", "자격", "신청자격", "신청대상"]):
        return "eligibility"
    if any(k in t for k in ["지원요건", "요건", "조건", "소득", "무주택", "연령", "자산", "기준"]):
        return "condition"
    if any(k in t for k in ["지원내용", "혜택", "지원금", "금액", "지원범위", "감면", "할인", "한도"]):
        return "benefit"
    if any(k in t for k in ["신청방법", "신청", "접수", "제출서류", "서류", "기간", "절차", "방법"]):
        return "apply"
    if any(k in t for k in ["문의", "연락처", "전화", "상담", "담당", "기관"]):
        return "contact"
    return "other"

# main normalize function
def normalize_housing_cost_etc(item: Dict[str, Any], seq_idx: int) -> Dict[str, Any]:

    title = norm_keep_lines(item.get("policy_title") or "")
    sections_in = item.get("sections") or []

    policy_id = make_seq_id("COST", seq_idx)

    target_texts: List[str] = []
    condition_texts: List[str] = []
    benefit_texts: List[str] = []
    apply_texts: List[str] = []
    contact_texts: List[str] = []

    for sec in sections_in:
        sec_title = sec.get("section_title") or sec.get("title") or ""
        sec_title_norm = norm_keep_lines(sec_title)

        lines: List[str] = []
        for t in (sec.get("texts") or []):
            if isinstance(t, str) and t.strip():
                lines.append(t)
        for tb in (sec.get("tables") or []):
            lines += table_to_lines(tb)

        cleaned = dedup_texts(lines)

        bucket = section_map(sec_title_norm)
        if bucket == "eligibility":
            target_texts += cleaned
        elif bucket == "condition":
            condition_texts += cleaned
        elif bucket == "benefit":
            benefit_texts += cleaned
        elif bucket == "apply":
            apply_texts += cleaned
        elif bucket == "contact":
            contact_texts += cleaned

    target_text = join_lines(target_texts) or None
    condition_text = join_lines(condition_texts) or None
    benefit_text = join_lines(benefit_texts) or None
    apply_text = join_lines(apply_texts) or None
    contact_text = join_lines(contact_texts) or None

    eligibility_text = "\n".join([t for t in [target_text, condition_text] if t]).strip() or None
    process_text = "\n".join([t for t in [apply_text, contact_text] if t]).strip() or None

    age_min, age_max = extract_age_range(eligibility_text or "")
    income_max_m = extract_income_max(eligibility_text or "")
    requires_no_house = detect_no_house(eligibility_text or "")
    regions = extract_regions(eligibility_text or "")

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
        "category": "housing_cost",
        "title": title,

        "eligibility_struct": eligibility_struct,

        "eligibility_text": eligibility_text,
        "benefit_text": benefit_text,
        "process_text": process_text,

        "provider": None,
        "region": None,
        "source_url": item.get("source_url"),
    }
