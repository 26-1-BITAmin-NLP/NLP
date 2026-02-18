# 2차 전처리 진행 코드

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.housing_agent.normalize.common import (
    dedup_texts,
    detect_no_house,
    extract_age_range,
    extract_income_max,
    extract_regions,
)

IN_PATH = ROOT / "data" / "processed" / "policies_v1.json"
OUT_PATH = ROOT / "data" / "processed" / "policies_v2.json"
REPORT_PATH = ROOT / "src" / "housing_agent" / "reports" / "secondary_preprocess_report.json"

RAW_DIR = ROOT / "data" / "raw"
RAW_FILES = {
    "finance": RAW_DIR / "금융지원_all.json",
    "housing_supply": RAW_DIR / "주택공급_all.json",
    "housing_cost": RAW_DIR / "주거비_기타지원_all.json",
    "dormitory": RAW_DIR / "기숙사_all.json",
}


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def split_lines(text: str) -> List[str]:
    return [ln.strip() for ln in (text or "").split("\n") if ln and ln.strip()]


def dedup_lines(lines: Iterable[str]) -> List[str]:
    return dedup_texts([x for x in lines if x and x.strip()])


def line_key(line: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", (line or "").lower())


APPLY_KW = [
    "신청", "접수", "절차", "방법", "제출서류", "모집", "기간", "기한", "방문", "온라인",
    "문의", "연락처", "상담", "콜센터", "전화", "홈페이지", "이의신청",
]
ELIGIBILITY_KW = [
    "지원대상", "대상자", "신청자격", "자격", "요건", "무주택", "소득", "자산", "연령",
    "세대주", "기준중위소득", "우선순위", "1순위", "2순위", "3순위", "가능한 자", "청년",
]
BENEFIT_KW = [
    "지원내용", "혜택", "지원금", "한도", "금리", "보증금", "임대료", "월세", "지급",
    "감면", "수용인원", "기숙사비", "서비스 내용", "최대", "만원", "억원",
]
PHONE_RE = r"\d{2,4}-\d{3,4}(?:-\d{4})?"


def score_by_keywords(text: str, keywords: List[str]) -> int:
    t = text or ""
    return sum(1 for k in keywords if k in t)


def line_scores(text: str) -> Tuple[int, int, int]:
    t = text or ""
    apply_score = score_by_keywords(t, APPLY_KW)
    eligibility_score = score_by_keywords(t, ELIGIBILITY_KW)
    benefit_score = score_by_keywords(t, BENEFIT_KW)

    if re.search(r"(1순위|2순위|3순위|4순위|5순위|우선|기준\s*중위소득|소득기준|무주택|세대주)", t):
        eligibility_score += 2
    if re.search(r"만?\s*\d{1,2}\s*세?\s*[~\-∼〜～]\s*만?\s*\d{1,2}\s*세|만?\s*\d{1,2}\s*세\s*(이상|이하|미만|초과)", t):
        eligibility_score += 2
    if re.search(r"(만원|억원|금리|한도|보증금|임대료|월세|지원금|지급|감면)", t):
        benefit_score += 2
    if re.search(r"(신청|접수|제출|문의|연락처|콜센터|홈페이지|방문|온라인|이의신청)", t):
        apply_score += 2
    if re.search(PHONE_RE, t):
        apply_score += 2

    return apply_score, eligibility_score, benefit_score


def bucket_from_title(section_title: str) -> str:
    t = (section_title or "").strip()
    if not t:
        return "unknown"

    apply_score, eligibility_score, benefit_score = line_scores(t)

    if apply_score > max(eligibility_score, benefit_score):
        return "process"
    if eligibility_score > max(apply_score, benefit_score):
        return "eligibility"
    if benefit_score > max(apply_score, eligibility_score):
        return "benefit"
    return "unknown"


def bucket_from_line(line: str) -> str:
    t = (line or "").strip()
    if not t:
        return "unknown"

    apply_score, eligibility_score, benefit_score = line_scores(t)

    if apply_score >= max(eligibility_score, benefit_score) and apply_score >= 2:
        return "process"
    if eligibility_score >= max(apply_score, benefit_score) and eligibility_score >= 2:
        return "eligibility"
    if benefit_score >= max(apply_score, eligibility_score) and benefit_score >= 2:
        return "benefit"
    return "unknown"


def final_bucket(section_title: str, line: str, fallback: str = "benefit") -> str:
    by_line = bucket_from_line(line)
    if by_line != "unknown":
        return by_line

    by_title = bucket_from_title(section_title)
    if by_title != "unknown":
        return by_title

    return fallback


def table_to_lines(tb: Dict[str, Any]) -> List[str]:
    headers = tb.get("headers") or []
    rows = tb.get("rows") or []
    out: List[str] = []
    if headers:
        out.append(" | ".join([str(x) for x in headers]))
    for row in rows:
        out.append(" | ".join([str(x) for x in row]))
    return out


def raw_units_finance(finance_raw: List[Dict[str, Any]]) -> Dict[str, List[Tuple[str, str]]]:
    out: Dict[str, List[Tuple[str, str]]] = {}
    for item in finance_raw:
        pid = item.get("policy_id")
        units: List[Tuple[str, str]] = []
        for sec in item.get("sections", []):
            title = sec.get("section_title") or sec.get("title") or ""
            current_inline_title = ""
            for line in (sec.get("texts") or []):
                if not isinstance(line, str):
                    continue
                s = line.strip()
                if not s:
                    continue

                # "사업내용" 같은 섹션 내부의 소제목 문맥을 유지
                if s in {"지원대상", "지원내용", "문의처", "신청방법", "신청절차", "자격요건"}:
                    current_inline_title = s
                    units.append((s, s))
                    continue

                effective_title = current_inline_title or title
                units.append((effective_title, s))
        out[pid] = units
    return out


def raw_units_housing_supply(supply_raw: List[Dict[str, Any]]) -> Dict[str, List[Tuple[str, str]]]:
    out: Dict[str, List[Tuple[str, str]]] = {}
    fields = [
        ("지원대상", "target_text"),
        ("자격요건", "condition_text"),
        ("지원내용", "benefit_text"),
        ("신청방법", "apply_text"),
        ("문의", "contact_text"),
    ]
    for idx, item in enumerate(supply_raw, start=1):
        pid = f"SUP_{idx:03d}"
        units: List[Tuple[str, str]] = []
        for title, key in fields:
            for line in split_lines(item.get(key) or ""):
                units.append((title, line))
        out[pid] = units
    return out


def raw_units_housing_cost(cost_raw: List[Dict[str, Any]]) -> Dict[str, List[Tuple[str, str]]]:
    out: Dict[str, List[Tuple[str, str]]] = {}

    # v1 생성 시 policy_title로 정렬 후 policy_id 부여
    sorted_items = sorted(cost_raw, key=lambda x: (x.get("policy_title") or "").strip())
    for idx, item in enumerate(sorted_items, start=1):
        pid = f"COST_{idx:03d}"
        units: List[Tuple[str, str]] = []
        for sec in item.get("sections", []):
            title = sec.get("section_title") or sec.get("title") or ""
            for line in (sec.get("texts") or []):
                if isinstance(line, str) and line.strip():
                    units.append((title, line.strip()))
            for tb in (sec.get("tables") or []):
                for line in table_to_lines(tb):
                    if line.strip():
                        units.append((title, line.strip()))
        out[pid] = units
    return out


def raw_units_dormitory(dorm_raw: List[Dict[str, Any]]) -> Dict[str, List[Tuple[str, str]]]:
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for item in dorm_raw:
        key = ((item.get("dorm_name") or "").strip(), (item.get("source_url") or "").strip())
        grouped[key].append(item)

    out: Dict[str, List[Tuple[str, str]]] = {}
    grouped_items = [grouped[k] for k in sorted(grouped.keys(), key=lambda x: (x[0], x[1]))]
    for idx, items in enumerate(grouped_items, start=1):
        pid = f"DORM_{idx:03d}"
        units: List[Tuple[str, str]] = []
        for row in items:
            title = (row.get("guide_section") or "").strip() or "기숙사 안내"
            for line in split_lines(row.get("guide_text") or ""):
                units.append((title, line))
        out[pid] = units
    return out


def build_raw_unit_index() -> Dict[str, List[Tuple[str, str]]]:
    finance_raw = load_json(RAW_FILES["finance"])
    supply_raw = load_json(RAW_FILES["housing_supply"])
    cost_raw = load_json(RAW_FILES["housing_cost"])
    dorm_raw = load_json(RAW_FILES["dormitory"])

    unit_index: Dict[str, List[Tuple[str, str]]] = {}
    unit_index.update(raw_units_finance(finance_raw))
    unit_index.update(raw_units_housing_supply(supply_raw))
    unit_index.update(raw_units_housing_cost(cost_raw))
    unit_index.update(raw_units_dormitory(dorm_raw))
    return unit_index


def recompute_eligibility_struct(policy: Dict[str, Any]) -> Dict[str, Any]:
    eligibility_text = policy.get("eligibility_text") or ""
    benefit_text = policy.get("benefit_text") or ""
    process_text = policy.get("process_text") or ""
    all_text = "\n".join([x for x in [eligibility_text, benefit_text, process_text] if x]).strip()
    region_field = policy.get("region") or ""

    age_min, age_max = extract_age_range(all_text)
    income_max_m = extract_income_max(all_text)
    requires_no_house = detect_no_house(all_text)

    primary_regions = extract_regions(region_field)
    if primary_regions.get("sido") or primary_regions.get("sigungu"):
        regions = primary_regions
    else:
        # region 필드가 없는 정책은 시/도만 완만하게 추출
        fallback = extract_regions(all_text)
        regions = {"sido": fallback.get("sido") or [], "sigungu": []}

    old_struct = policy.get("eligibility_struct") or {}
    return {
        "age_min": age_min,
        "age_max": age_max,
        "income_max_m": income_max_m,
        "asset_max_m": old_struct.get("asset_max_m"),
        "household_types": old_struct.get("household_types") or [],
        "requires_no_house": requires_no_house,
        "regions": regions,
        "housing_types": old_struct.get("housing_types") or [],
    }


def improve_policy(policy: Dict[str, Any], raw_units: List[Tuple[str, str]]) -> Tuple[Dict[str, Any], Dict[str, int]]:
    out = dict(policy)
    buckets = {"eligibility": [], "benefit": [], "process": []}
    stats = {
        "moved_benefit_to_process": 0,
        "moved_benefit_to_eligibility": 0,
        "moved_process_to_eligibility": 0,
        "moved_process_to_benefit": 0,
        "added_from_raw": 0,
    }

    # 기존 텍스트에서 명확한 오분류만 이동
    for line in split_lines(policy.get("eligibility_text") or ""):
        buckets["eligibility"].append(line)

    for line in split_lines(policy.get("benefit_text") or ""):
        apply_score, eligibility_score, benefit_score = line_scores(line)
        if re.search(r"만?\s*\d{1,2}\s*세?\s*[~\-∼〜～]\s*만?\s*\d{1,2}\s*세|만?\s*\d{1,2}\s*세\s*(이상|이하|미만|초과)", line):
            buckets["eligibility"].append(line)
            stats["moved_benefit_to_eligibility"] += 1
        elif re.search(PHONE_RE, line) and benefit_score == 0:
            buckets["process"].append(line)
            stats["moved_benefit_to_process"] += 1
        elif apply_score >= 3 and benefit_score == 0 and eligibility_score <= 1:
            buckets["process"].append(line)
            stats["moved_benefit_to_process"] += 1
        else:
            buckets["benefit"].append(line)

    for line in split_lines(policy.get("process_text") or ""):
        apply_score, eligibility_score, benefit_score = line_scores(line)
        if eligibility_score >= 3 and apply_score <= 1:
            buckets["eligibility"].append(line)
            stats["moved_process_to_eligibility"] += 1
        elif benefit_score >= 3 and apply_score == 0:
            buckets["benefit"].append(line)
            stats["moved_process_to_benefit"] += 1
        else:
            buckets["process"].append(line)

    # raw 대비 누락된 문장 보완
    existing_keys = {line_key(x) for xs in buckets.values() for x in xs if line_key(x)}
    existing_blob = line_key("\n".join([x for xs in buckets.values() for x in xs]))
    for sec_title, line in raw_units:
        key = line_key(line)
        if not key or len(key) <= 2 or key in existing_keys or key in existing_blob:
            continue

        bucket = final_bucket(sec_title, line, fallback="benefit")
        buckets[bucket].append(line)
        existing_keys.add(key)
        existing_blob += key
        stats["added_from_raw"] += 1

    out["eligibility_text"] = "\n".join(dedup_lines(buckets["eligibility"])) or None
    out["benefit_text"] = "\n".join(dedup_lines(buckets["benefit"])) or None
    out["process_text"] = "\n".join(dedup_lines(buckets["process"])) or None
    out["eligibility_struct"] = recompute_eligibility_struct(out)

    return out, stats


def empty_field_counts(policies: List[Dict[str, Any]]) -> Dict[str, int]:
    fields = ["eligibility_text", "benefit_text", "process_text"]
    return {
        f"{f}_empty": sum(1 for p in policies if not (p.get(f) or "").strip())
        for f in fields
    }


""" def main() -> None:
    policies_v1 = load_json(IN_PATH)
    raw_unit_index = build_raw_unit_index()

    improved: List[Dict[str, Any]] = []
    per_policy_report: List[Dict[str, Any]] = []

    total_stats = {
        "policy_count": len(policies_v1),
        "raw_mapped_count": 0,
        "raw_unmapped_count": 0,
        "moved_benefit_to_process": 0,
        "moved_benefit_to_eligibility": 0,
        "moved_process_to_eligibility": 0,
        "moved_process_to_benefit": 0,
        "added_from_raw": 0,
    }

    for p in policies_v1:
        pid = p.get("policy_id")
        has_raw_key = pid in raw_unit_index
        raw_units = raw_unit_index.get(pid) or []
        if has_raw_key:
            total_stats["raw_mapped_count"] += 1
        else:
            total_stats["raw_unmapped_count"] += 1

        p2, stats = improve_policy(p, raw_units)
        improved.append(p2)

        for k in (
            "moved_benefit_to_process",
            "moved_benefit_to_eligibility",
            "moved_process_to_eligibility",
            "moved_process_to_benefit",
            "added_from_raw",
        ):
            total_stats[k] += stats[k]

        per_policy_report.append({
            "policy_id": pid,
            "title": p.get("title"),
            "category": p.get("category"),
            **stats,
        })

    save_json(OUT_PATH, improved)
    report = {
        "summary": {
            **total_stats,
            "before_empty_counts": empty_field_counts(policies_v1),
            "after_empty_counts": empty_field_counts(improved),
        },
        "per_policy": per_policy_report,
    }
    save_json(REPORT_PATH, report)

    print(f"saved: {OUT_PATH}")
    print(f"saved: {REPORT_PATH}")
    print(f"summary: {report['summary']}")


if __name__ == "__main__":
    main() """
