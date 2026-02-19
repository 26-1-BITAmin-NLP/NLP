# 금융 지원 데이터 정규화 코드
from __future__ import annotations
from typing import Any, Dict, List, Tuple
import re

from src.housing_agent.normalize.common import (
    norm_keep_lines,
    dedup_texts,
    join_lines,
    extract_age_range,
    extract_income_max,
    detect_no_house,
    extract_regions,
)

# 섹션 제목을 기준으로 bucket 분류
def section_map(title: str) -> str:

    t = norm_keep_lines(title)

    if any(k in t for k in ["대출 대상", "지원 대상", "자격", "대상자", "대상"]):
        return "eligibility"

    if any(k in t for k in ["신청 시기", "신청 기간", "신청 방법", "신청 절차", "제출 서류", "신청"]):
        return "apply"

    if any(k in t for k in ["상담문의", "문의", "연락처", "업무취급은행"]):
        return "contact"

    if any(k in t for k in [
        "대상 주택", "대출 한도", "대출금리", "이용기간", "상환방법", "우대금리",
        "고객부담비용", "중도상환수수료", "유의사항", "담보", "평가"
    ]):
        return "benefit"

    # 명확히 분류 안 되는 경우
    return "other"

# eligibility 내부 분리
COND_KEYWORDS = [
    "소득", "연소득", "총소득", "자산", "순자산", "가액", "기준", "이하", "이내", "초과",
    "억원", "만원", "%", "점수",
    "무주택", "중복", "미이용", "불가", "제외", "금지", "연체", "부도", "대위변제", "대지급",
    "신용", "신용도", "신용정보", "금융질서문란", "공공 기록", "특수 기록", "신용회복",
    "요건", "조건", "다만", "단,", "예외", "충족", "상환", "해지", "철회", "의무",
    "계약", "접수일", "신청일", "실행일", "3개월", "6개월", "1년", "기간",
]

def is_condition_line(line: str) -> bool:
    if re.search(r"\d", line):
        return True
    return any(k in line for k in COND_KEYWORDS)

def split_target_condition(lines: List[str]) -> Tuple[List[str], List[str]]:
    target: List[str] = []
    cond: List[str] = []

    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if is_condition_line(s):
            cond.append(s)
        else:
            target.append(s)

    return target, cond

# main normalize function
def normalize_finance(raw: Dict[str, Any]) -> Dict[str, Any]:

    policy_id = raw.get("policy_id")
    title = raw.get("policy_name") or raw.get("title") or ""
    source_url = raw.get("source_url")

    eligibility_lines: List[str] = []
    benefit_lines: List[str] = []
    apply_lines: List[str] = []
    contact_lines: List[str] = []
    other_lines: List[str] = []

    for sec in raw.get("sections", []):
        sec_title = sec.get("section_title") or sec.get("title") or ""
        texts = dedup_texts(sec.get("texts", []))

        bucket = section_map(sec_title)

        if bucket == "eligibility":
            eligibility_lines += texts
        elif bucket == "benefit":
            benefit_lines += texts
        elif bucket == "apply":
            apply_lines += texts
        elif bucket == "contact":
            contact_lines += texts
        else:
            other_lines += texts

    # other로 분리된 경우 재분배
    for t in other_lines:
        s = (t or "").strip()
        if not s:
            continue

        if ("지원대상" in s) or ("대상" in s and "문의" not in s):
            eligibility_lines.append(s)

        elif any(k in s for k in ["문의", "문의처", "연락", "전화", "콜센터", "TEL", "Tel", "☎"]):
            contact_lines.append(s)

        else:
            benefit_lines.append(s)

    # text 생성
    target_lines, condition_lines = split_target_condition(eligibility_lines)

    target_text = join_lines(target_lines) or None
    condition_text = join_lines(condition_lines) or None

    eligibility_text = "\n".join([t for t in [target_text, condition_text] if t]).strip() or None
    benefit_text = join_lines(benefit_lines) or None
    process_text = join_lines(dedup_texts(apply_lines + contact_lines)) or None

    # eligibility_struct 생성
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

    # 최종 스키마 반환
    return {
        "policy_id": policy_id,
        "category": "finance",
        "title": title,

        "eligibility_struct": eligibility_struct,

        "eligibility_text": eligibility_text,
        "benefit_text": benefit_text,
        "process_text": process_text,

        "provider": None,
        "region": None,
        "source_url": source_url,
    }
