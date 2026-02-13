# 주거비/기타 지원 데이터 정규화 코드
from __future__ import annotations

from typing import Any, Dict, List
from src.housing_agent.normalize.common import (
    stable_id, norm_keep_lines, dedup_texts, join_lines, wrap_long_lines
)

# table을 line으로 변환
def _table_to_lines(tb: Dict[str, Any]) -> List[str]:
    headers = tb.get("headers") or []
    rows = tb.get("rows") or []
    lines: List[str] = []
    if headers:
        lines.append(" | ".join([str(x) for x in headers]))
    for r in rows:
        lines.append(" | ".join([str(x) for x in r]))
    return lines

# sections title, texts 매핑
def _section_map(title: str) -> str:

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


def normalize_housing_cost_etc(item: Dict[str, Any]) -> Dict[str, Any]:
    title = norm_keep_lines(item.get("policy_title") or "")
    sections_in = item.get("sections") or []

    policy_id = stable_id("COST", {"policy_title": title, "sections": sections_in})

    target_texts: List[str] = []
    condition_texts: List[str] = []
    benefit_texts: List[str] = []
    apply_texts: List[str] = []
    contact_texts: List[str] = []

    for sec in sections_in:
        sec_title = sec.get("section_title") or sec.get("title") or ""
        sec_title_norm = norm_keep_lines(sec_title)

        # texts, tables을 lines로 출력
        lines: List[str] = []
        for t in (sec.get("texts") or []):
            if isinstance(t, str) and t.strip():
                lines.append(t)
        for tb in (sec.get("tables") or []):
            lines += _table_to_lines(tb)

        cleaned = dedup_texts(lines)

        bucket = _section_map(sec_title_norm)
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

    parts: List[str] = [f"제목: {title}", "카테고리: housing_cost", ""]
    if target_text:
        parts += ["[대상/자격]", target_text, ""]
    if condition_text:
        parts += ["[조건]", condition_text, ""]
    if benefit_text:
        parts += ["[혜택/지원내용]", benefit_text, ""]
    if apply_text:
        parts += ["[신청]", apply_text, ""]
    if contact_text:
        parts += ["[문의]", contact_text, ""]

    raw_text = "\n".join([p for p in parts if p is not None]).strip()
    raw_text = wrap_long_lines(raw_text, max_line_len=110)

    return {
        "policy_id": policy_id,
        "category": "housing_cost",
        "title": title,
        "region": None,
        "provider": None,
        "source_url": None,
        "target_text": target_text,
        "condition_text": condition_text,
        "benefit_text": benefit_text,
        "apply_text": apply_text,
        "contact_text": contact_text,
        "raw_text": raw_text,
    }
