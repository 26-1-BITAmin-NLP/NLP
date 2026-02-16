# 기숙사 정책 데이터 정규화 코드
from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
import re

from src.housing_agent.normalize.common import (
    make_seq_id,
    # norm_keep_lines,
    dedup_texts,
    extract_age_range,
    extract_income_max,
    detect_no_house,
    extract_regions,
)

def grouping_key(item: Dict[str, Any]) -> Tuple[str, str]:
    return (item.get("dorm_name") or "").strip(), (item.get("source_url") or "").strip()

TOKEN_RE = re.compile(r"[A-Za-z_]+")

def section_tokens(section: str) -> List[str]:
    s = (section or "").strip().lower().replace("[", " ").replace("]", " ")
    return TOKEN_RE.findall(s)

def fallback_bucket_from_tokens(tokens: List[str]) -> Optional[str]:
    t = set(tokens)
    if "schedule" in t:
        return "apply"
    if t & {"selection", "restriction"}:
        return "condition"
    if "eligibility" in t:
        return "target"
    if t & {"fee_payment", "capacity"}:
        return "benefit"
    return None

HEADER_TO_BUCKET = {
    "입사자격": "target",
    "지원대상": "target",
    "신청자격": "target",
    "자격요건": "target",
    "대상": "target",

    "선발기준": "condition",
    "선발방법": "condition",
    "선발": "condition",
    "제한": "condition",
    "제외": "condition",
    "벌점": "condition",
    "규정": "condition",

    "신청기간": "apply",
    "신청방법": "apply",
    "모집기간": "apply",
    "접수기간": "apply",
    "제출서류": "apply",
    "입금(등록)": "apply",
    "입금": "apply",
    "등록": "apply",
    "정규입사": "apply",
    "입사절차": "apply",
    "입사 절차": "apply",
    "배정": "apply",
    "개인정보등록": "apply",
    "개인정보 등록": "apply",
    "환불": "apply",
    "퇴사": "apply",

    "기숙사비": "benefit",
    "생활관비": "benefit",
    "비용": "benefit",
    "납부": "benefit",
}

def as_header(line: str) -> Optional[str]:
    s = (line or "").strip()
    if not s:
        return None
    if len(s) > 25:
        return None
    if s in HEADER_TO_BUCKET:
        return s
    for h in HEADER_TO_BUCKET.keys():
        if s.startswith(h):
            return h
    return None

def is_contact_line(line: str) -> bool:
    s = line or ""
    return any(k in s for k in ["문의", "연락", "전화", "담당", "TEL", "Tel", "☎", "콜센터"])

def split_lines(text: str) -> List[str]:
    lines = [ln.strip() for ln in (text or "").split("\n") if ln.strip()]
    cleaned = []
    for ln in lines:
        cleaned.append(re.sub(r"^\s*([\-•*]|[0-9]+\.)\s*", "", ln).strip())
    return [c for c in cleaned if c]

def route_guide_text(guide_text: str, guide_section: str) -> Dict[str, List[str]]:
    tokens = section_tokens(guide_section)
    fallback = fallback_bucket_from_tokens(tokens)

    out = {"target": [], "condition": [], "apply": [], "benefit": [], "contact": [], "other": []}
    current_bucket: Optional[str] = None

    for line in split_lines(guide_text):
        if is_contact_line(line):
            out["contact"].append(line)

        header = as_header(line)
        if header:
            current_bucket = HEADER_TO_BUCKET[header]
            out[current_bucket].append(header)
            continue

        if current_bucket:
            out[current_bucket].append(line)
        else:
            if fallback:
                out[fallback].append(line)
            else:
                out["other"].append(line)

    for k in out.keys():
        out[k] = dedup_texts(out[k])
    return out

def pick_num(items: List[Dict[str, Any]], key: str):
    for it in items:
        v = it.get(key)
        if v in (None, "", 0):
            continue
        return v
    v = items[0].get(key)
    return None if v in (None, "", 0) else v

# main normalize function
def normalize_dormitory_group(items: List[Dict[str, Any]], seq_idx: int) -> Dict[str, Any]:
    base = items[0]
    dorm_name = (base.get("dorm_name") or "").strip()
    source_url = base.get("source_url") or None

    capacity = pick_num(items, "capacity")
    fee_1p = pick_num(items, "fee_1p_kkrw")
    fee_2p = pick_num(items, "fee_2p_kkrw")
    fee_3p = pick_num(items, "fee_3p_kkrw")
    fee_4p = pick_num(items, "fee_4p_plus_kkrw")

    fee_parts: List[str] = []
    if fee_1p is not None: fee_parts.append(f"1인실= {fee_1p}천원")
    if fee_2p is not None: fee_parts.append(f"2인실= {fee_2p}천원")
    if fee_3p is not None: fee_parts.append(f"3인실= {fee_3p}천원")
    if fee_4p is not None: fee_parts.append(f"4인+= {fee_4p}천원")

    numeric_benefit = " / ".join([
        f"수용인원: {capacity}" if capacity is not None else "수용인원: 정보없음",
        ("기숙사비: " + ", ".join(fee_parts)) if fee_parts else "기숙사비: 정보없음",
    ])

    target_lines: List[str] = []
    condition_lines: List[str] = []
    apply_lines: List[str] = []
    benefit_lines: List[str] = []
    contact_lines: List[str] = []

    for it in items:
        sec = (it.get("guide_section") or "").strip() or "안내"
        txt = (it.get("guide_text") or "").strip()
        if not txt:
            continue

        routed = route_guide_text(txt, sec)
        target_lines += routed["target"]
        condition_lines += routed["condition"]
        apply_lines += routed["apply"]
        benefit_lines += routed["benefit"]
        contact_lines += routed["contact"]

    target_text = "\n".join(dedup_texts(target_lines)).strip() if target_lines else None
    condition_text = "\n".join(dedup_texts(condition_lines)).strip() if condition_lines else None
    apply_text = "\n".join(dedup_texts(apply_lines)).strip() if apply_lines else None
    contact_text = "\n".join(dedup_texts(contact_lines)).strip() if contact_lines else None

    extra_benefit = "\n".join(dedup_texts(benefit_lines)).strip() if benefit_lines else None
    benefit_text = numeric_benefit if not extra_benefit else (numeric_benefit + "\n" + extra_benefit)

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
        "housing_types": ["기숙사"],
    }

    policy_id = make_seq_id("DORM", seq_idx)

    return {
        "policy_id": policy_id,
        "category": "dormitory",
        "title": dorm_name,

        "eligibility_struct": eligibility_struct,

        "eligibility_text": eligibility_text,
        "benefit_text": benefit_text,
        "process_text": process_text,

        "provider": None,
        "region": None,
        "source_url": source_url,
    }

def normalize_dormitory(all_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for it in all_items:
        groups.setdefault(grouping_key(it), []).append(it)

    grouped_items = [groups[k] for k in sorted(groups.keys(), key=lambda x: (x[0], x[1]))]
    return [normalize_dormitory_group(items, idx) for idx, items in enumerate(grouped_items, start=1)]