# 주택 공급 데이터 정규화 코드
from __future__ import annotations

from typing import Any, Dict
from src.housing_agent.normalize.common import make_seq_id

def normalize_housing_supply(item: Dict[str, Any], seq_idx: int | None = None) -> Dict[str, Any]:

    policy_id = make_seq_id("SUP", seq_idx) if seq_idx is not None else str(item["policy_id"]).strip()
    title = (item.get("title") or "").strip()

    target_text = (item.get("target_text") or "").strip()
    condition_text = (item.get("condition_text") or "").strip()
    benefit_text = (item.get("benefit_text") or "").strip()
    apply_text = (item.get("apply_text") or "").strip()
    contact_text = (item.get("contact_text") or "").strip()

    parts = [f"제목: {title}", "카테고리: housing_supply"]
    if item.get("region"):
        parts.append(f"지역: {item.get('region')}")
    if item.get("provider"):
        parts.append(f"기관: {item.get('provider')}")
    if target_text:
        parts.append(f"대상: {target_text}")
    if condition_text:
        parts.append(f"조건: {condition_text}")
    if benefit_text:
        parts.append(f"혜택: {benefit_text}")
    if apply_text:
        parts.append(f"신청: {apply_text}")
    if contact_text:
        parts.append(f"문의: {contact_text}")

    raw_text = "\n".join(parts).strip()

    return {
        "policy_id": policy_id,
        "category": "housing_supply",
        "title": title,
        "region": item.get("region"),
        "provider": item.get("provider"),
        "source_url": item.get("source_url"),

        "target_text": item.get("target_text"),
        "condition_text": item.get("condition_text"),
        "benefit_text": item.get("benefit_text"),
        "apply_text": item.get("apply_text"),
        "contact_text": item.get("contact_text"),

        "raw_text": raw_text,
    }