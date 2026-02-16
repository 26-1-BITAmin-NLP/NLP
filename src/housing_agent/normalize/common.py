# 카테고리 별 공통 정규화 코드
from __future__ import annotations
from typing import Any, Dict, List
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
def extract_age_range(text: str):
    if not text:
        return None, None

    m = re.search(r"(\d+)\s*~\s*(\d+)\s*세", text)
    if m:
        return int(m.group(1)), int(m.group(2))

    min_m = re.search(r"(\d+)\s*세\s*이상", text)
    max_m = re.search(r"(\d+)\s*세\s*이하", text)

    return (
        int(min_m.group(1)) if min_m else None,
        int(max_m.group(1)) if max_m else None,
    )

# 소득 최대값 추출
def extract_income_max(text: str):
    if not text:
        return None

    m = re.search(r"(\d+)\s*만원\s*이하", text)
    if m:
        return int(m.group(1))

    return None

# 무주택 여부
def detect_no_house(text: str):
    if not text:
        return None
    if "무주택" in text:
        return True
    return None

# 지역명 추출 (시/도, 시/군/구)
def extract_regions(text: str):
    if not text:
        return {"sido": [], "sigungu": []}

    sido_list = []
    for sido in ["서울", "경기", "부산", "대구", "인천", "광주", "대전", "울산"]:
        if sido in text:
            sido_list.append(sido)

    return {
        "sido": sido_list,
        "sigungu": []
    }
