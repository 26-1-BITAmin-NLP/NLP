# 기숙사 데이터 정규화 코드
from __future__ import annotations

from typing import Any, Dict, List, Tuple
from src.housing_agent.normalize.common import stable_id, norm_keep_lines, dedup_texts, wrap_long_lines

# 기숙사 별로 그룹핑
def _group_key(item: Dict[str, Any]) -> Tuple[str, str]:
    return (item.get("dorm_name") or "").strip(), (item.get("source_url") or "").strip()

# guide_section 토큰화
def _section_tokens(section: str) -> List[str]:
    s = (section or "").strip()
    if not s:
        return []
    return [t.strip() for t in s.split("\n") if t.strip()]


def _bucket_from_tokens(tokens: List[str]) -> str:
    tset = set(tokens)

    if "eligibility" in tset:
        return "target"

    if tset & {"selection", "restriction"}:
        return "condition"

    if "schedule" in tset:
        return "apply"

    return "other"


def normalize_dormitory_group(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    base = items[0]
    dorm_name = (base.get("dorm_name") or "").strip()
    category = (base.get("category") or "").strip()
    source_url = base.get("source_url") or None

    def pick_num(key: str):
        for it in items:
            v = it.get(key)
            if v not in (None, "", 0):
                return v
        return base.get(key)

    capacity = pick_num("capacity")
    fee_1p = pick_num("fee_1p_kkrw")
    fee_2p = pick_num("fee_2p_kkrw")
    fee_3p = pick_num("fee_3p_kkrw")
    fee_4p = pick_num("fee_4p_plus_kkrw")

    fee_parts: List[str] = []
    if fee_1p is not None: fee_parts.append(f"1인실:{fee_1p}천원")
    if fee_2p is not None: fee_parts.append(f"2인실:{fee_2p}천원")
    if fee_3p is not None: fee_parts.append(f"3인실:{fee_3p}천원")
    if fee_4p is not None: fee_parts.append(f"4인+:{fee_4p}천원")

    benefit_text = " / ".join([
        f"수용인원:{capacity}" if capacity is not None else "수용인원:정보없음",
        ("기숙사비:" + ", ".join(fee_parts)) if fee_parts else "기숙사비:정보없음",
    ])

    sections_map: Dict[str, List[str]] = {}
    for it in items:
        sec = (it.get("guide_section") or "").strip() or "안내"
        txt = (it.get("guide_text") or "").strip()
        if txt:
            sections_map.setdefault(sec, []).append(txt)

    sections: List[Dict[str, Any]] = []
    for sec_title, texts in sections_map.items():
        cleaned = dedup_texts(texts)
        if cleaned:
            sections.append({"title": norm_keep_lines(sec_title), "texts": cleaned})

    target_texts = []
    condition_texts = []
    apply_texts = []

    for s in sections:
        tokens = _section_tokens(s["title"])
        bucket = _bucket_from_tokens(tokens)

        if bucket == "target":
            target_texts += s["texts"]
        elif bucket == "condition":
            condition_texts += s["texts"]
        elif bucket == "apply":
            apply_texts += s["texts"]

    target_text = "\n".join(target_texts).strip() if target_texts else None
    condition_text = "\n".join(condition_texts).strip() if condition_texts else None
    apply_text = "\n".join(apply_texts).strip() if apply_texts else None

    contact_text = None

    parts: List[str] = [
        f"제목: {dorm_name}",
        "카테고리: dormitory",
        f"유형: {category}" if category else "",
        f"혜택: {benefit_text}",
        f"링크: {source_url}" if source_url else "",
        "",
        "[조건/자격]", condition_text or "정보 없음",
        "",
        "[혜택/비용]", benefit_text,
    ]
    if apply_text:
        parts += ["", "[신청]", apply_text]

    parts.append("")
    for s in sections:
        parts.append(f"[{s['title']}]")
        parts.extend(s["texts"])
        parts.append("")

    raw_text = "\n".join([p for p in parts if p is not None]).strip()
    raw_text = wrap_long_lines(raw_text, max_line_len=110)

    policy_id = stable_id("DORM", {"dorm_name": dorm_name, "source_url": source_url})

    return {
        "policy_id": policy_id,
        "category": "dormitory",
        "title": dorm_name,
        "region": None,
        "provider": None,
        "source_url": source_url,

        "target_text": target_text,
        "condition_text": condition_text,
        "benefit_text": benefit_text,
        "apply_text": apply_text,
        "contact_text": contact_text,

        # "sections": sections,
        "raw_text": raw_text,
    }


def normalize_dormitory(all_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for it in all_items:
        groups.setdefault(_group_key(it), []).append(it)
    return [normalize_dormitory_group(items) for items in groups.values()]
