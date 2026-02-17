# 전체 데이터 청킹
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple


INPUT_PATH = "data/processed/policies.json"
OUTPUT_PATH = "data/processed/policies_chunking.jsonl"

MAX_CHARS = 1100        # chunk 최대 길이
OVERLAP = 160           # chunk 오버랩 (긴 텍스트 자를 때 사용)

MIN_CHARS = 300         # 너무 짧은 chunk는 병합 (최적화)
MIN_KEEP = 120          # 마지막 청크가 120보다 짧으면 이전 chunk에 붙임

MIN_POLICY_CHUNK = 250  # (정책 전체) 너무 짧은 chunk는 이전 chunk에 병합
DROP_UNDER = 40         # 40보다 짧은 길이는 노이즈로 생각하고 버림

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

# 긴 텍스트 분할
def _split_with_overlap(text: str, max_chars: int, overlap: int) -> List[str]:

    text = _norm_lines(text)
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    # 문단 단위
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

            # 문단이 너무 길면 줄 단위로 분할
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

    # max_chars를 넘는 청크가 있으면 글자 단위로 분할, overlap
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

# 청킹 최적화 (짧은 조각 chunk 병합)
def _merge_short_pieces(pieces: List[str], min_chars: int, min_keep: int) -> List[str]:
    pieces = [p for p in (pieces or []) if _norm_lines(p)]
    if not pieces:
        return []

    merged: List[str] = []
    buf = ""

    for p in pieces:
        p = _norm_lines(p)
        if not buf:
            buf = p
            continue

        # buf가 짧으면 계속 붙임
        if len(buf) < min_chars:
            buf = buf + "\n\n" + p
        else:
            merged.append(buf)
            buf = p

    if buf:
        merged.append(buf)

    # 마지막 조각이 너무 짧으면 이전 청크에 붙임
    if len(merged) >= 2 and len(merged[-1]) < min_keep:
        merged[-2] = _norm_lines(merged[-2] + "\n\n" + merged[-1])
        merged.pop()

    return merged

# raw_text 보완 시 기존 섹션들과의 중복 엄격하게 체크
def _build_blocks(p: Dict[str, Any]) -> List[Tuple[str, str]]:
    blocks: List[Tuple[str, str]] = []

    meta = _meta_block(p)
    if meta:
        blocks.append(("META", meta))

    existing_content = meta
    non_empty_fields = 0

    for key, sec in SECTION_ORDER[1:]:
        txt = _norm_lines(p.get(key) or "")
        if txt:
            non_empty_fields += 1
            blocks.append((sec, txt))
            existing_content += "\n" + txt

    # 필드가 너무 적을 때만 raw_text를 참고, 기존 내용과 겹치면 제외
    if non_empty_fields <= 1:
        raw = _norm_lines(p.get("raw_text") or "")
        if raw and len(raw) > len(existing_content):
            # 메타데이터의 내용이 raw_text 시작 부분에 있다면 제거
            raw = _strip_meta_prefix_from_raw(raw, meta)
            if raw and len(raw) > 50: # 의미 있는 길일 때만 추가
                 blocks.append(("EXTRA", raw))
    return blocks

# 아주 짧은 청크 처리 (최적화)
def _policy_level_merge(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not chunks:
        return []
    
    out: List[Dict[str, Any]] = []
    
    for c in chunks:
        text = _norm_lines(c.get("text") or "")
        if len(text) < DROP_UNDER:
            continue

        if not out:
            out.append(c)
            continue

        # 이전 청크와 섹션이 같고, 현재 텍스트가 너무 짧을 때만 합침
        if out[-1]["section"] == c["section"] and len(text) < MIN_POLICY_CHUNK:
            out[-1]["text"] = _norm_lines(out[-1]["text"] + "\n\n" + text)
        else:
            out.append(c)

    return out

# metadata 중복 제거
def _strip_meta_prefix_from_raw(raw_text: str, meta_text: str) -> str:

    raw = _norm_lines(raw_text)
    meta = _norm_lines(meta_text)
    if not raw or not meta:
        return raw

    # raw_text가 meta로 시작하면 그 부분 제거
    if raw.startswith(meta):
        raw = _norm_lines(raw[len(meta):])
        return raw.lstrip("\n").strip()

    return raw

def chunk_policy(p: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks = _build_blocks(p)
    chunks: List[Dict[str, Any]] = []
    idx = 0

    for section, block_text in blocks:
        # meta 데이터 쪼개지 않기
        if section == "META":
            pieces = [_norm_lines(block_text)] if _norm_lines(block_text) else []
        else:
            pieces = _split_with_overlap(block_text, MAX_CHARS, OVERLAP)
            pieces = _merge_short_pieces(pieces, MIN_CHARS, MIN_KEEP)

        for piece in pieces:
            piece = _norm_lines(piece)
            if not piece:
                continue
            chunks.append({
                "chunk_id": f"{p['policy_id']}#{idx:03d}",
                "policy_id": p["policy_id"],
                "category": p.get("category"),
                "title": p.get("title"),
                "section": section,
                "text": piece,
                # "source_url": p.get("source_url"),
            })
            idx += 1

    chunks = _policy_level_merge(chunks)

    for new_i, c in enumerate(chunks):
        c["chunk_id"] = f"{p['policy_id']}#{new_i:03d}"

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
