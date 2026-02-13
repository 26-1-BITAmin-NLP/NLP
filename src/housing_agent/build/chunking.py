# 전체 데이터 청킹
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple


INPUT_PATH = "data/processed/policies.json"
OUTPUT_PATH = "data/processed/policies_chunking.jsonl"

MAX_CHARS = 1100        # chunk 최대 길이
OVERLAP = 160           # chunk 오버랩

# 청킹 데이터 섹션 설정
SECTION_ORDER: List[Tuple[str, str]] = [
    ("meta", "META"),
    ("target_text", "TARGET"),
    ("condition_text", "CONDITION"),
    ("benefit_text", "BENEFIT"),
    ("apply_text", "APPLY"),
    ("contact_text", "CONTACT"),
]

# 공백 및 줄바꿈 정리
def _norm_lines(s: str) -> str:

    if not s:
        return ""
    lines = [ln.rstrip() for ln in s.split("\n")]

    out = []
    empty = 0
    for ln in lines:
        if ln.strip() == "":
            empty += 1
            if empty <= 2:
                out.append("")
        else:
            empty = 0
            out.append(ln.strip())
    return "\n".join(out).strip()

def _meta_block(p: Dict[str, Any]) -> str:
    lines = [
        f"제목: {p.get('title','')}",
        f"카테고리: {p.get('category','')}",
    ]
    if p.get("region"):
        lines.append(f"지역: {p['region']}")
    if p.get("provider"):
        lines.append(f"기관: {p['provider']}")
    if p.get("source_url"):
        lines.append(f"링크: {p['source_url']}")
    return _norm_lines("\n".join(lines))

# 긴 텍스트 나누기
def _split_with_overlap(text: str, max_chars: int, overlap: int) -> List[str]:

    text = _norm_lines(text)
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    # 1) 문단 단위
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    buf = ""

    def flush():
        nonlocal buf
        if buf.strip():
            chunks.append(buf.strip())
        buf = ""

    for para in paras:
        candidate = para if not buf else (buf + "\n\n" + para)
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            flush()

            if len(para) > max_chars:
                lines = [ln for ln in para.split("\n") if ln.strip()]
                b = ""
                for ln in lines:
                    cand = ln if not b else (b + "\n" + ln)
                    if len(cand) <= max_chars:
                        b = cand
                    else:
                        if b:
                            chunks.append(b)
                        b = ln
                if b:
                    chunks.append(b)
            else:
                buf = para
    flush()

    final: List[str] = []
    for c in chunks:
        if len(c) <= max_chars:
            final.append(c)
        else:
            start = 0
            while start < len(c):
                end = min(len(c), start + max_chars)
                piece = c[start:end].strip()
                if piece:
                    final.append(piece)
                if end == len(c):
                    break
                start = max(0, end - overlap)

    return final

# 결과 리스트 반환
def _build_blocks(p: Dict[str, Any]) -> List[Tuple[str, str]]:
    blocks: List[Tuple[str, str]] = []

    meta = _meta_block(p)
    if meta:
        blocks.append(("META", meta))

    non_empty_fields = 0

    for key, sec in SECTION_ORDER[1:]:
        txt = _norm_lines(p.get(key) or "")
        if txt:
            non_empty_fields += 1
            blocks.append((sec, txt))

    # 필드가 거의 비어있으면 raw_text로 보완
    if non_empty_fields <= 1:
        raw = _norm_lines(p.get("raw_text") or "")
        if raw:
            blocks.append(("EXTRA", raw))

    return blocks

def chunk_policy(p: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks = _build_blocks(p)

    chunks: List[Dict[str, Any]] = []
    idx = 0
    for section, block_text in blocks:
        pieces = _split_with_overlap(block_text, MAX_CHARS, OVERLAP)
        for piece in pieces:
            chunks.append({
                "chunk_id": f"{p['policy_id']}#{idx:03d}",
                "policy_id": p["policy_id"],
                "category": p.get("category"),
                "title": p.get("title"),
                "section": section,
                "text": piece,
                "source_url": p.get("source_url"),
            })
            idx += 1
    return chunks

def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        policies = json.load(f)

    all_chunks: List[Dict[str, Any]] = []
    for p in policies:
        all_chunks.extend(chunk_policy(p))

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"policies: {len(policies)}") # 정책 개수
    print(f"chunks: {len(all_chunks)}") # 청킹 개수

if __name__ == "__main__":
    main()
