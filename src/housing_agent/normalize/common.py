# 카테고리 별 공통 정규화 코드
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import re

# import hashlib
# import json

# 해시 함수
""" def stable_id(prefix: str, payload: Dict[str, Any]) -> str:
    s = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    h = hashlib.md5(s.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{h}" """

# 정책 id 생성 방안 수정
def make_seq_id(prefix: str, idx: int) -> str:
    return f"{prefix}_{idx:03d}"

# 줄바꿈 및 공백 제거
def norm_keep_lines(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    lines: List[str] = []
    for ln in s.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        ln = re.sub(r"[ \t]+", " ", ln)
        lines.append(ln)
    return "\n".join(lines)

# raw_text wrapping
def wrap_long_lines(text: str, max_line_len: int = 120) -> str:
    out: List[str] = []
    for line in (text or "").split("\n"):
        line = line.strip()
        if not line:
            continue

        if len(line) <= max_line_len:
            out.append(line)
            continue

        parts = re.split(r"(?<=[\.\!\?])\s+|(?<=;)\s+|(?<=·)\s+", line)
        buf = ""
        for p in parts:
            p = p.strip()
            if not p:
                continue
            if not buf:
                buf = p
            elif len(buf) + 1 + len(p) <= max_line_len:
                buf = f"{buf} {p}"
            else:
                out.append(buf)
                buf = p
        if buf:
            out.append(buf)

    return "\n".join(out)


def join_lines(texts: List[str]) -> str:
    return "\n".join([t for t in (texts or []) if (t or "").strip()]).strip()


def dedup_texts(texts: List[str]) -> List[str]:

    cleaned = [norm_keep_lines(t) for t in (texts or []) if norm_keep_lines(t)]

    # 완전 중복 제거
    uniq: List[str] = []
    seen = set()
    for t in cleaned:
        if t not in seen:
            seen.add(t)
            uniq.append(t)

    # 잡음 제거
    def is_noise(t: str) -> bool:
        if len(t) <= 2:
            return True
        if re.fullmatch(r"\d{2,4}-\d{3,4}-\d{4}", t) or re.fullmatch(r"\d{3,4}-\d{4}", t):
            return True
        if t in {"홈페이지 바로가기", "바로가기"}:
            return True
        return False

    uniq = [t for t in uniq if not is_noise(t)]

    # substring 제거
    final: List[str] = []
    for i, t in enumerate(uniq):
        contained = False
        for j, u in enumerate(uniq):
            if i != j and len(t) < len(u) and t in u:
                contained = True
                break
        if not contained:
            final.append(t)

    return final

# 데이터 구조화 유틸 함수 추가

# 나이 숫자 추출
def extract_age_range(text: str) -> Tuple[Optional[int], Optional[int]]:
    if not text:
        return None, None

    m = re.search(r"만?\s*(\d{1,2})\s*세?\s*[~\-∼〜～]\s*만?\s*(\d{1,2})\s*세", text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return (a, b) if a <= b else (b, a)

    min_age = None
    max_age = None

    min_m = re.search(r"만?\s*(\d{1,2})\s*세\s*(이상|초과)", text)
    if min_m:
        base = int(min_m.group(1))
        min_age = base + (1 if min_m.group(2) == "초과" else 0)

    max_m = re.search(r"만?\s*(\d{1,2})\s*세\s*(이하|미만)", text)
    if max_m:
        base = int(max_m.group(1))
        max_age = base - (1 if max_m.group(2) == "미만" else 0)

    if min_age is not None and max_age is not None and min_age > max_age:
        return None, None

    return min_age, max_age

# 소득 최대값 추출
def extract_income_max(text: str) -> Optional[int]:
    if not text:
        return None

    # 소득 문맥에서만 추출해 차량/기타 금액 오탐을 줄임
    income_context = r"(소득|연소득|월소득|기준중위소득|도시근로자)"

    m = re.search(rf"{income_context}[^\n]{{0,20}}(\d+)\s*만원\s*이하", text)
    if m:
        return int(m.group(2))

    # "연소득 4천 이하" 형태
    m = re.search(rf"{income_context}[^\n]{{0,20}}(\d+)\s*천\s*이하", text)
    if m:
        return int(m.group(2)) * 1000

    return None

# 무주택 여부
def detect_no_house(text: str):
    if not text:
        return None
    if "무주택" in text:
        return True
    return None

# 지역명 추출 (시/도, 시/군/구)
def extract_regions(text: str) -> Dict[str, List[str]]:
    if not text:
        return {"sido": [], "sigungu": []}

    # 지역명은 단어 경계 기준으로 잡아 '세대구성원' 같은 오탐을 방지
    mapping = [
        ("서울", [r"서울특별시", r"서울시", r"서울"]),
        ("부산", [r"부산광역시", r"부산시", r"부산"]),
        ("대구", [r"대구광역시", r"대구시", r"대구"]),
        ("인천", [r"인천광역시", r"인천시", r"인천"]),
        ("광주", [r"광주광역시", r"광주시", r"광주"]),
        ("대전", [r"대전광역시", r"대전시", r"대전"]),
        ("울산", [r"울산광역시", r"울산시", r"울산"]),
        ("세종", [r"세종특별자치시", r"세종시", r"세종"]),
        ("경기", [r"경기도", r"경기"]),
        ("강원", [r"강원특별자치도", r"강원도", r"강원"]),
        ("충북", [r"충청북도", r"충북"]),
        ("충남", [r"충청남도", r"충남"]),
        ("전북", [r"전북특별자치도", r"전라북도", r"전북"]),
        ("전남", [r"전라남도", r"전남"]),
        ("경북", [r"경상북도", r"경북"]),
        ("경남", [r"경상남도", r"경남"]),
        ("제주", [r"제주특별자치도", r"제주도", r"제주"]),
    ]

    sido_list: List[str] = []
    for canonical, variants in mapping:
        for v in variants:
            if re.search(rf"(?<![가-힣A-Za-z0-9]){v}(?![가-힣A-Za-z0-9])", text):
                sido_list.append(canonical)
                break

    sigungu_candidates = re.findall(r"(?<![가-힣A-Za-z0-9])([가-힣]{1,12}(?:시|군|구))(?![가-힣A-Za-z0-9])", text)
    sigungu_list: List[str] = []
    for name in sigungu_candidates:
        # 광역/도 단위 행정명은 제외
        if any(x in name for x in ["특별시", "광역시", "자치시", "자치도"]):
            continue
        if name.endswith("도시"):
            continue
        if any(x in name for x in ["신청", "접수", "입사", "소득", "가구", "지원", "대상", "자격", "무주택", "증가", "감소", "가능", "해당", "대출"]):
            continue
        if name not in sigungu_list:
            sigungu_list.append(name)

    return {
        "sido": sido_list,
        "sigungu": sigungu_list,
    }
