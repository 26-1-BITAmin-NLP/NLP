# 금융 지원 데이터 정규화 코드
from __future__ import annotations

from typing import Any, Dict, List, Tuple
import re

from src.housing_agent.normalize.common import (
    norm_keep_lines, dedup_texts, join_lines, wrap_long_lines
)

# sections title, texts 매핑
def _section_map(title: str) -> str:

    t = norm_keep_lines(title)

    if any(k in t for k in ["대출 대상", "지원 대상", "자격", "대상자"]):
        return "eligibility"
    if any(k in t for k in ["신청 시기", "신청 기간", "신청 방법", "신청 절차", "제출 서류"]):
        return "apply"
    if any(k in t for k in ["상담문의", "문의", "연락처", "업무취급은행"]):
        return "contact"
    if any(k in t for k in [
        "대상 주택", "대출 한도", "대출금리", "이용기간", "상환방법", "우대금리",
        "고객부담비용", "중도상환수수료", "유의사항", "담보", "평가"
    ]):
        return "benefit_or_rule"
    return "other"

# eligibility 텍스트를 target과 condition 으로 분리
COND_KEYWORDS = [
    # 정량/기준
    "소득", "연소득", "총소득", "자산", "순자산", "가액", "기준", "이하", "이내", "초과",
    "억원", "만원", "%", "점수",
    # 제한/금지/검증
    "무주택", "중복", "미이용", "불가", "제외", "금지", "연체", "부도", "대위변제", "대지급",
    "신용", "신용도", "신용정보", "금융질서문란", "공공 기록", "특수 기록", "신용회복",
    # 요건/예외/조건
    "요건", "조건", "다만", "단,", "예외", "충족", "상환", "해지", "철회", "의무",
    # 계약/기간/접수 관련(대상보단 조건 성격이 강함)
    "계약", "접수일", "신청일", "실행일", "3개월", "6개월", "1년", "기간",
]

TARGET_HINTS = [
    # 대상 라벨/집단
    "청년", "신혼", "다자녀", "한부모", "장애인", "다문화", "생애최초",
    # 신분/구성
    "세대주", "세대원", "미혼", "성년", "배우자", "직계", "단독세대",
    # 그냥 대상 서술에 자주 등장
    "대상", "자격", "대출 대상", "지원 대상"
]


def _is_condition_line(line: str) -> bool:
    t = line.strip()

    # 숫자/단위가 있으면 조건일 가능성 높음
    if re.search(r"\d", t):
        return True

    # 조건 키워드 포함 여부
    return any(k in t for k in COND_KEYWORDS)


def _split_target_condition(lines: List[str]) -> Tuple[List[str], List[str]]:

    target: List[str] = []
    cond: List[str] = []

    for ln in lines:
        t = ln.strip()
        if not t:
            continue

        # 조건이 명확하면 condition
        if _is_condition_line(t):
            cond.append(t)
            continue

        # 조건이 명확하지 않으면, 대상 힌트가 있으면 target
        if any(k in t for k in TARGET_HINTS):
            target.append(t)
        else:
            target.append(t)

    return target, cond


def normalize_finance(raw: Dict[str, Any]) -> Dict[str, Any]:
    policy_id = raw.get("policy_id")
    title = raw.get("policy_name") or raw.get("title") or ""
    source_url = raw.get("source_url")

    eligibility_lines: List[str] = []
    apply_texts: List[str] = []
    contact_texts: List[str] = []
    benefit_texts: List[str] = []

    for sec in raw.get("sections", []):
        sec_title = sec.get("section_title") or sec.get("title") or ""
        texts = dedup_texts(sec.get("texts", []))

        bucket = _section_map(sec_title)
        if bucket == "eligibility":
            eligibility_lines += texts
        elif bucket == "apply":
            apply_texts += texts
        elif bucket == "contact":
            contact_texts += texts
        elif bucket == "benefit_or_rule":
            benefit_texts += texts

    # 스키마 분리
    target_lines, condition_lines = _split_target_condition(eligibility_lines)

    target_text = join_lines(target_lines) or None
    condition_text = join_lines(condition_lines) or None
    benefit_text = join_lines(benefit_texts) or None
    apply_text = join_lines(apply_texts) or None
    contact_text = join_lines(contact_texts) or None

    # raw_text 포맷 설정
    parts: List[str] = [
        f"제목: {title}",
        "카테고리: finance",
        f"링크: {source_url}" if source_url else "",
        "",
    ]
    if target_text:
        parts += ["[대상/자격]", target_text, ""]
    if condition_text:
        parts += ["[세부조건]", condition_text, ""]
    if benefit_text:
        parts += ["[혜택/규정]", benefit_text, ""]
    if apply_text:
        parts += ["[신청]", apply_text, ""]
    if contact_text:
        parts += ["[문의]", contact_text, ""]

    raw_text = "\n".join([p for p in parts if p is not None]).strip()
    raw_text = wrap_long_lines(raw_text, max_line_len=120)

    return {
        "policy_id": policy_id,
        "category": "finance",
        "title": title,
        "region": None,
        "provider": None,
        "source_url": source_url,
        "target_text": target_text,
        "condition_text": condition_text,
        "benefit_text": benefit_text,
        "apply_text": apply_text,
        "contact_text": contact_text,
        "raw_text": raw_text,
    }