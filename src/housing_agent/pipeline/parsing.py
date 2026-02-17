# policies_v1 -> policies_v2
# eligibility_struct 변수 보강 코드

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[3]

IN_PATH = ROOT / "data" / "processed" / "policies_v1.json"
OUT_PATH = ROOT / "data" / "processed" / "policies_v2.json"

REPORT_DIR = ROOT / "src" / "housing_agent" / "reports"
REPORT_PATH = REPORT_DIR / "eligibility_struct_report.json"


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# 텍스트 정리 유틸 함수

def clean_text(s: str) -> str:
    if not s:
        return ""
    t = str(s)
    t = t.replace("\u00a0", " ")
    t = re.sub(r"[,·]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def merge_texts(*parts: str) -> str:
    xs = [p for p in parts if p and str(p).strip()]
    return "\n".join(xs)


# age 파싱 함수

def _clean_age_text(text: str) -> str:
    if not text:
        return ""
    t = str(text)
    t = t.replace(",", "")
    t = re.sub(r"\s+", " ", t).strip()
    return t

def parse_age_range(text: str) -> Tuple[Optional[int], Optional[int], Optional[str]]:

    t = _clean_age_text(text)
    if not t:
        return None, None, None

    # 가장 명확한 범위 우선: 19~34세
    m = re.search(r"만?\s*(\d{1,2})\s*[~\-]\s*만?\s*(\d{1,2})\s*세", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        lo, hi = (a, b) if a <= b else (b, a)
        return lo, hi, m.group(0)

    # 단일 조건들을 모두 수집해서 교집합 계산
    min_age = None
    max_age = None
    ev = []

    # 이상/초과
    for mm in re.finditer(r"만?\s*(\d{1,2})\s*세\s*(이상|초과)", t):
        base = int(mm.group(1))
        # 초과(>)면 정수 최소는 +1, 이상(>=)면 그대로
        cand = base + (1 if mm.group(2) == "초과" else 0)
        min_age = cand if min_age is None else max(min_age, cand)
        ev.append(mm.group(0))

    # 이하/미만
    for mm in re.finditer(r"만?\s*(\d{1,2})\s*세\s*(이하|미만)", t):
        base = int(mm.group(1))

        cand = base - (1 if mm.group(2) == "미만" else 0)
        max_age = cand if max_age is None else min(max_age, cand)
        ev.append(mm.group(0))

    # 불가능한 구간이면 None 처리
    if min_age is not None and max_age is not None and min_age > max_age:
        return None, None, "INFEASIBLE: " + " / ".join(ev)

    return min_age, max_age, (" / ".join(ev) if ev else None)


# 금액 파싱 함수

def money_to_won(expr: str) -> Optional[int]:

    t = clean_text(expr)
    if not t:
        return None

    # 공백 제거하여 단순화
    compact = t.replace(" ", "")

    total = 0

    # 억 단위
    m_uk = re.search(r"(\d+(?:\.\d+)?)억", compact)
    if m_uk:
        total += int(float(m_uk.group(1)) * 100_000_000)

    # 천만원 단위 (예: 5천만원)
    m_cheonman = re.search(r"(\d+(?:\.\d+)?)천만원", compact)
    if m_cheonman:
        total += int(float(m_cheonman.group(1)) * 10_000_000)

    # 만원 단위 (예: 3700만원, 5000만원, 250만원)
    m_manwon = re.search(r"(\d+(?:\.\d+)?)만원", compact)
    if m_manwon:
        total += int(float(m_manwon.group(1)) * 10_000)

    # 만 원 (띄어쓰기)
    m_man = re.search(r"(\d+(?:\.\d+)?)만(?:원)?", compact)
    if m_man and "만원" not in compact:
        total += int(float(m_man.group(1)) * 10_000)

    # 순수 원 단위 (앞에서 못 잡았을 때)
    m_won = re.search(r"(\d+(?:\.\d+)?)원", compact)
    if m_won and total == 0:
        total = int(float(m_won.group(1)))

    return total if total > 0 else None


# income 파싱 함수

def parse_income(text: str) -> Dict[str, Any]:

    t = clean_text(text)
    ev: List[str] = []

    monthly = None
    annual = None
    median_ratio = None

    # 기준중위소득 120%
    m = re.search(r"기준\s*중위\s*소득\s*(\d+)\s*%", t)
    if m:
        median_ratio = int(m.group(1))
        ev.append(m.group(0))

    # 연소득 ~ 억/천만원/만원
    m = re.search(r"(연\s*소득|연소득)\s*([0-9\.]+\s*억\s*원?|[0-9\.]+\s*천\s*만원|[0-9\.]+\s*만원)", t)
    if m:
        val = money_to_won(m.group(2))
        if val:
            annual = val
            ev.append(m.group(0))

    # 월소득/월평균소득
    m = re.search(r"(월\s*소득|월소득|월\s*평균\s*소득|월평균소득)\s*([0-9\.]+\s*만원)", t)
    if m:
        val = money_to_won(m.group(2))
        if val:
            monthly = val
            ev.append(m.group(0))

    # 애매한 "소득 5000만원 이하" (연/월 표기가 없으면 연으로 추정하되 evidence 남김)
    if annual is None:
        m = re.search(r"소득\s*([0-9\.]+\s*억\s*원?|[0-9\.]+\s*천\s*만원|[0-9\.]+\s*만원)", t)
        if m:
            val = money_to_won(m.group(1))
            if val:
                annual = val
                ev.append("AMBIGUOUS:" + m.group(0))

    return {
        "monthly_max_won": monthly,
        "annual_max_won": annual,
        "median_ratio_max": median_ratio,
        "evidence": ev,
    }


# asset 파싱 함수

def parse_asset(text: str) -> Dict[str, Any]:

    t = clean_text(text)
    ev = None
    total_max = None

    m = re.search(r"(총\s*자산|자산)\s*([0-9\.]+\s*억\s*원?|[0-9\.]+\s*천\s*만원|[0-9\.]+\s*만원)", t)
    if m:
        val = money_to_won(m.group(2))
        if val:
            total_max = val
            ev = m.group(0)

    return {"total_max_won": total_max, "evidence": ev}


# 무주택 조건 파싱 함수

def parse_requires_no_house(text: str) -> Tuple[Optional[bool], Optional[str]]:

    t = clean_text(text).replace(" ", "")
    if not t:
        return None, None

    # 유주택 허용/무주택 요건 없음
    if any(k in t for k in ["유주택", "주택보유", "무주택요건없", "무주택제한없", "무주택아님"]):
        return False, "유주택/무주택요건없음 패턴"

    if "무주택" in t:
        return True, "무주택 포함"

    return None, None


# region 파싱 함수

SIDO = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
]

def parse_region(region_field: str, text: str) -> Dict[str, Any]:

    rf = clean_text(region_field)
    t = clean_text(text)
    evidence: List[str] = []

    # 전국
    merged = merge_texts(rf, t)
    if re.search(r"(전국|전\s*국|전국단위|전국민)", merged):
        return {
            "scope": "nationwide",
            "regions": {"sido": [], "sigungu": []},
            "evidence": ["전국 패턴"],
        }

    sido: List[str] = []

    # region_field 기반
    if rf:
        for s in SIDO:
            if s in rf:
                sido.append(s)
                evidence.append(f"region_field:{s}")

    # fallback: 접미어 있는 경우
    if not sido:
        for s in SIDO:
            if re.search(rf"{s}(특별시|광역시|특별자치시|특별자치도|도|시)", merged):
                sido.append(s)
                evidence.append(f"text_suffix:{s}")

    # 중복 제거
    uniq = []
    for x in sido:
        if x not in uniq:
            uniq.append(x)

    scope = "local" if uniq else "unknown"
    return {
        "scope": scope,
        "regions": {"sido": uniq, "sigungu": []},
        "evidence": evidence,
    }


# eligibility_struct_v2 생성

def build_struct_v2(policy: Dict[str, Any]) -> Dict[str, Any]:

    eligibility_text = policy.get("eligibility_text") or ""
    benefit_text = policy.get("benefit_text") or ""
    process_text = policy.get("process_text") or ""
    region_field = policy.get("region") or ""
    provider = policy.get("provider") or ""

    all_text = merge_texts(eligibility_text, benefit_text, process_text, region_field, provider)

    min_age, max_age, age_ev = parse_age_range(all_text)
    income = parse_income(all_text)
    asset = parse_asset(all_text)
    no_house, no_house_ev = parse_requires_no_house(all_text)
    region = parse_region(region_field, all_text)

    return {

        "min_age": min_age,
        "max_age": max_age,

        "income_monthly_max_won": income["monthly_max_won"],
        "income_annual_max_won": income["annual_max_won"],
        "income_median_ratio_max": income["median_ratio_max"],

        "asset_total_max_won": asset["total_max_won"],

        "requires_no_house": no_house,

        "region_scope": region["scope"],
        "regions": region["regions"],

        # 디버깅용
        "evidence": {
            "age": age_ev,
            "income": income["evidence"],
            "asset": asset["evidence"],
            "requires_no_house": no_house_ev,
            "region": region["evidence"],
        },
    }


def main() -> None:
    policies = load_json(IN_PATH)

    enriched: List[Dict[str, Any]] = []
    for p in policies:
        p2 = dict(p)

        # 기존 eligibility_struct_v2 추가만
        p2["eligibility_struct_v2"] = build_struct_v2(p2)
        enriched.append(p2)

    save_json(OUT_PATH, enriched)

if __name__ == "__main__":
    main()
