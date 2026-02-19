# 데이터 청킹 진행 코드

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[3]

INPUT_PATH = ROOT / "data" / "processed" / "policies_v2.json"
OUTPUT_PATH = ROOT / "data" / "processed" / "policies_v2_chunked.jsonl"
META_MAP_PATH = ROOT / "data" / "processed" / "policies_v2_metadata.json"

# 임베딩 모델 일반 권장 기준 : 700~1200 chars
MAX_CHARS = 900
OVERLAP = 120
MIN_CHARS = 180
DROP_UNDER = 35

SECTION_ORDER: List[Tuple[str, str]] = [
    ("meta", "META"),
    ("eligibility_text", "ELIGIBILITY"),
    ("benefit_text", "BENEFIT"),
    ("process_text", "PROCESS"),
]


def _norm_text(s: str) -> str:
    if not s:
        return ""
    lines = [ln.rstrip() for ln in str(s).split("\n")]
    out: List[str] = []
    blank = 0
    for ln in lines:
        if ln.strip():
            out.append(ln.strip())
            blank = 0
        else:
            blank += 1
            if blank <= 1:
                out.append("")
    return "\n".join(out).strip()


def _meta_block(p: Dict[str, Any]) -> str:
    es = p.get("eligibility_struct") or {}
    regions = es.get("regions") or {}

    lines = [
        f"제목: {p.get('title', '')}",
        f"카테고리: {p.get('category', '')}",
    ]

    if p.get("provider"):
        lines.append(f"기관: {p['provider']}")
    if p.get("region"):
        lines.append(f"지역: {p['region']}")
    if es.get("age_min") is not None or es.get("age_max") is not None:
        lines.append(f"나이: {es.get('age_min')}~{es.get('age_max')}")
    if regions.get("sido"):
        lines.append(f"시도: {', '.join(regions['sido'])}")
    if regions.get("sigungu"):
        lines.append(f"시군구: {', '.join(regions['sigungu'])}")
    if p.get("source_url"):
        lines.append(f"출처: {p['source_url']}")

    return _norm_text("\n".join(lines))


def _split_long_text(text: str, max_chars: int, overlap: int) -> List[str]:
    text = _norm_text(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    # 문단 우선 분할 -> 너무 길면 줄 단위 -> 마지막 fallback 문자 단위
    paras = [x.strip() for x in text.split("\n\n") if x.strip()]
    chunks: List[str] = []
    buf = ""

    def flush() -> None:
        nonlocal buf
        if buf.strip():
            chunks.append(buf.strip())
        buf = ""

    for para in paras:
        cand = para if not buf else f"{buf}\n\n{para}"
        if len(cand) <= max_chars:
            buf = cand
            continue

        flush()
        if len(para) <= max_chars:
            buf = para
            continue

        lines = [x.strip() for x in para.split("\n") if x.strip()]
        line_buf = ""
        for ln in lines:
            line_cand = ln if not line_buf else f"{line_buf}\n{ln}"
            if len(line_cand) <= max_chars:
                line_buf = line_cand
            else:
                if line_buf:
                    chunks.append(line_buf)
                line_buf = ln
        if line_buf:
            chunks.append(line_buf)

    flush()

    final_chunks: List[str] = []
    for c in chunks:
        if len(c) <= max_chars:
            final_chunks.append(c)
            continue

        start = 0
        while start < len(c):
            end = min(len(c), start + max_chars)
            piece = c[start:end].strip()
            if piece:
                final_chunks.append(piece)
            if end == len(c):
                break
            start = max(0, end - overlap)

    return final_chunks


def _merge_short_chunks(pieces: List[str], min_chars: int) -> List[str]:
    pieces = [_norm_text(x) for x in pieces if _norm_text(x)]
    if not pieces:
        return []

    out: List[str] = []
    buf = ""
    for p in pieces:
        if not buf:
            buf = p
            continue
        if len(buf) < min_chars:
            buf = _norm_text(f"{buf}\n\n{p}")
        else:
            out.append(buf)
            buf = p
    if buf:
        out.append(buf)
    return out


def _build_blocks(policy: Dict[str, Any]) -> List[Tuple[str, str]]:
    blocks: List[Tuple[str, str]] = []

    meta = _meta_block(policy)
    if meta:
        blocks.append(("META", meta))

    for key, sec_name in SECTION_ORDER[1:]:
        text = _norm_text(policy.get(key) or "")
        if text:
            blocks.append((sec_name, text))

    return blocks


def chunk_policy(policy: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks = _build_blocks(policy)
    out: List[Dict[str, Any]] = []
    idx = 0

    for section, text in blocks:
        if section == "META":
            pieces = [text]
        else:
            pieces = _split_long_text(text, MAX_CHARS, OVERLAP)
            pieces = _merge_short_chunks(pieces, MIN_CHARS)

        for piece in pieces:
            piece = _norm_text(piece)
            if not piece or len(piece) < DROP_UNDER:
                continue
            out.append(
                {
                    "chunk_id": f"{policy['policy_id']}#{idx:03d}",
                    "policy_id": policy["policy_id"],
                    "category": policy.get("category"),
                    "title": policy.get("title"),
                    "section": section,
                    "text": piece,
                }
            )
            idx += 1

    return out


def build_policy_metadata_map(policies: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for p in policies:
        pid = p.get("policy_id")
        if not pid:
            continue
        out[pid] = {
            "eligibility_struct": p.get("eligibility_struct"),
            "source_url": p.get("source_url"),
        }
    return out


def main() -> None:
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        policies = json.load(f)

    all_chunks: List[Dict[str, Any]] = []
    for p in policies:
        all_chunks.extend(chunk_policy(p))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for row in all_chunks:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    meta_map = build_policy_metadata_map(policies)
    with open(META_MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(meta_map, f, ensure_ascii=False, indent=2)

    print(f"input_policies: {len(policies)}")
    print(f"output_chunks: {len(all_chunks)}")
    print(f"saved: {OUTPUT_PATH}")
    print(f"saved: {META_MAP_PATH}")


if __name__ == "__main__":
    main()
