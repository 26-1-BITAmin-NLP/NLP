# 사용자에게 관련성이 높은 정책 정보를 반환하도록 랭킹, 필터링을 진행하는 코드

"""
입력
- 사용자 질의 문자열
- FAISS 인덱스
- vector_idx, chunk 메타 매핑
- 원본 청크 텍스트

출력
- 유사도 상위 k개 청크 (점수, policy_id, chunk_id, 미리보기 텍스트)
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import numpy as np
from dotenv import load_dotenv

import faiss
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INDEX_PATH = ROOT / "data" / "vectorstore" / "policies_v2_index.faiss"
DEFAULT_INDEX_LOG_PATH = ROOT / "data" / "vectorstore" / "policies_v2_index_log.json"
DEFAULT_MAPPING_PATH = ROOT / "data" / "vectorstore" / "policies_v2_embedding_mapping.jsonl"
DEFAULT_CHUNK_PATH = ROOT / "data" / "processed" / "policies_v2_chunked.jsonl"
DEFAULT_METADATA_PATH = ROOT / "data" / "processed" / "policies_v2_metadata.json" # 정책 단위 metadata 결합
DEFAULT_SECTION_WEIGHTS = "META=0.92,ELIGIBILITY=1.10,BENEFIT=1.03,PROCESS=1.00" # 섹션별 defalut 가중치
ALL_CATEGORIES = ("finance", "housing_supply", "housing_cost", "dormitory")
ALL_SECTIONS = ("META", "ELIGIBILITY", "BENEFIT", "PROCESS")

# 질의 의도 추정을 위한 카테고리별 키워드 사전
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "finance": [
        "대출", "금리", "융자", "상환", "보증금", "전세자금", "보증료", "이자", "담보", "기금",
    ],
    "housing_supply": [
        "행복주택", "공공임대", "매입임대", "전세임대", "주택공급", "분양", "청약", "입주자모집", "입주",
    ],
    "housing_cost": [
        "월세", "임대료", "주거비", "관리비", "주거급여", "보조금", "임차료", "주거비용",
    ],
    "dormitory": [
        "기숙사", "생활관", "사생", "입사", "퇴사", "호실",
    ],
}

# 질의 의도 추정을 위한 섹션별 키워드 사전
SECTION_KEYWORDS: Dict[str, List[str]] = {
    "ELIGIBILITY": [
        "자격", "조건", "대상", "요건", "연령", "나이", "소득", "무주택", "가능", "해당",
    ],
    "BENEFIT": [
        "혜택", "지원금", "금액", "얼마", "한도", "금리", "지원내용", "얼마나", "보조",
    ],
    "PROCESS": [
        "신청", "절차", "방법", "기간", "접수", "서류", "문의", "어떻게", "언제",
    ],
    "META": [
        "출처", "기관", "운영", "정책명", "어느 지역", "어디", "개요",
    ],
}


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(description="FAISS 기반 정책 Retriever")
    parser.add_argument("--query", type=str, required=True, help="사용자 질의")
    parser.add_argument("--top-k", type=int, default=5, help="최종 반환 개수")
    parser.add_argument("--search-k", type=int, default=0, help="1차 검색 개수")
    parser.add_argument("--query-model", type=str, default="", help="질의 임베딩 모델")
    parser.add_argument("--api-key-env", type=str, default="OPENAI_API_KEY", help="OpenAI API Key")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH, help="FAISS 인덱스 경로")
    parser.add_argument("--index-log", type=Path, default=DEFAULT_INDEX_LOG_PATH, help="인덱스 로그 json 경로")
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING_PATH, help="vector mapping jsonl 경로")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNK_PATH, help="원본 chunk jsonl 경로")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_PATH, help="정책 메타데이터 json 경로")
    parser.add_argument("--age", type=int, default=-1, help="나이 필터(미사용: -1)")
    parser.add_argument("--region-sido", type=str, default="", help="시/도 필터")
    parser.add_argument("--region-sigungu", type=str, default="", help="시/군/구 필터")
    parser.add_argument("--disable-section-weight", action="store_true", help="섹션 가중치 랭킹 비활성화")
    parser.add_argument("--section-weights", type=str, default=DEFAULT_SECTION_WEIGHTS, help="섹션별 가중치")
    parser.add_argument("--disable-dynamic-section-weight", action="store_true", help="질의 의도 기반 섹션 가중치 비활성화")
    parser.add_argument("--disable-dynamic-category-weight", action="store_true", help="질의 의도 기반 카테고리 가중치 비활성화")
    parser.add_argument("--disable-text-dedup", action="store_true", help="텍스트 중복 제거 비활성화")
    parser.add_argument("--text-dedup-min-len", type=int, default=80, help="텍스트 dedup 최소 길이")
    parser.add_argument("--preview-chars", type=int, default=300, help="본문 미리보기 글자 수")
    parser.add_argument("--json", action="store_true", help="JSON으로 출력")
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL 파싱 오류: {path}:{line_no}") from exc
    return rows


def normalize(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm == 0.0:
        return vec
    return vec / norm


def embed_query(client: Any, model: str, query: str) -> np.ndarray:
    resp = client.embeddings.create(model=model, input=[query])
    return np.asarray(resp.data[0].embedding, dtype=np.float32)


def build_chunk_map(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(r.get("chunk_id")): r for r in rows if r.get("chunk_id")}

# 섹션별 기본 가중치 파싱
def parse_section_weights(raw: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"section-weights 형식 오류: '{part}'")
        k, v = part.split("=", 1)
        key = k.strip().upper()
        try:
            val = float(v.strip())
        except ValueError as exc:
            raise ValueError(f"section-weights 값 오류: '{part}'") from exc
        if val <= 0:
            raise ValueError(f"section-weights는 0보다 커야 합니다: '{part}'")
        out[key] = val
    return out

# 섹션별 동적 가중치 추론
def infer_dynamic_section_weights(query: str) -> tuple[Dict[str, float], Dict[str, int]]:
    q = (query or "").strip().lower()
    q_nospace = re.sub(r"\s+", "", q)

    scores: Dict[str, int] = {sec: 0 for sec in ALL_SECTIONS}
    for sec, keywords in SECTION_KEYWORDS.items():
        hit = 0
        for kw in keywords:
            k = kw.lower()
            if k in q or k in q_nospace:
                hit += 1
        scores[sec] = hit

    max_score = max(scores.values()) if scores else 0
    if max_score <= 0:
        return ({sec: 1.0 for sec in ALL_SECTIONS}, scores)

    active = [sec for sec, sc in scores.items() if sc > 0]
    weights: Dict[str, float] = {}
    for sec in ALL_SECTIONS:
        sc = scores.get(sec, 0)
        if sc <= 0:
            weights[sec] = 0.97
            continue
        ratio = sc / max_score
        weights[sec] = round(1.05 + (0.08 * ratio), 3)

    if len(active) == 1 and max_score >= 2:
        main_sec = active[0]
        for sec in ALL_SECTIONS:
            if sec != main_sec and scores.get(sec, 0) == 0:
                weights[sec] = 0.94

    return weights, scores

# 카테고리별 동적 가중치 추론
def infer_dynamic_category_weights(query: str) -> tuple[Dict[str, float], Dict[str, int]]:
    q = (query or "").strip().lower()
    q_nospace = re.sub(r"\s+", "", q)

    scores: Dict[str, int] = {cat: 0 for cat in ALL_CATEGORIES}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        hit = 0
        for kw in keywords:
            k = kw.lower()
            if k in q or k in q_nospace:
                hit += 1
        scores[cat] = hit

    max_score = max(scores.values()) if scores else 0
    if max_score <= 0:
        return ({cat: 1.0 for cat in ALL_CATEGORIES}, scores)

    active = [cat for cat, sc in scores.items() if sc > 0]
    weights: Dict[str, float] = {}
    for cat in ALL_CATEGORIES:
        sc = scores.get(cat, 0)
        if sc <= 0:
            weights[cat] = 0.96
            continue
        # active category는 1.06~1.14 범위에서 가점
        ratio = sc / max_score
        weights[cat] = round(1.06 + (0.08 * ratio), 3)

    # 의도가 한 카테고리에 강하게 쏠리면 비해당 카테고리를 더 감점
    if len(active) == 1 and max_score >= 2:
        main_cat = active[0]
        for cat in ALL_CATEGORIES:
            if cat != main_cat and scores.get(cat, 0) == 0:
                weights[cat] = 0.93

    return weights, scores


def compute_rank_score(
    raw_score: float,
    metric: str,
    section: str,
    section_weights: Dict[str, float],
    category: str,
    category_weights: Dict[str, float],
) -> float:

    base = raw_score if metric != "l2" else -raw_score
    section_weight = section_weights.get((section or "").upper(), 1.0)
    category_weight = category_weights.get((category or "").lower(), 1.0)
    return base * section_weight * category_weight


# 텍스트 중복 제거용 키 생성 : 공백 제거, 특수문자 제거, 소문자화
def build_text_key(text: str, min_len: int) -> str:
    if not text:
        return ""
    t = text.strip()
    if len(t) < min_len:
        return ""
    return re.sub(r"[^\w가-힣]+", "", t.lower())


# 지역 비교 정규화
def _region_normalize(value: str) -> str:
    return (value or "").strip().replace(" ", "")

# 지역 매치 비교
def _region_match(query_region: str, policy_regions: List[str]) -> bool:
    q = _region_normalize(query_region)
    if not q:
        return True
    norm_regions = [_region_normalize(x) for x in policy_regions if str(x).strip()]
    if not norm_regions:
        # 지역 정보 비어 있으면 통과
        return True
    for r in norm_regions:
        if q == r or q in r or r in q:
            return True
    return False


def _policy_passes_filters(
    policy_meta: Dict[str, Any],
    age: Optional[int],
    region_sido: str,
    region_sigungu: str,
) -> bool:
    
    # 정책 단위 나이/지역 필터 적용
    es = (policy_meta or {}).get("eligibility_struct") or {}

    if age is not None:
        age_min = es.get("age_min")
        age_max = es.get("age_max")
        if age_min is not None and age < int(age_min):
            return False
        if age_max is not None and age > int(age_max):
            return False

    regions = es.get("regions") or {}
    sido_list = regions.get("sido") or []
    sigungu_list = regions.get("sigungu") or []

    if region_sido and not _region_match(region_sido, sido_list):
        return False
    if region_sigungu and not _region_match(region_sigungu, sigungu_list):
        return False

    return True


def build_allowed_policy_ids(
    metadata: Dict[str, Any],
    age: Optional[int],
    region_sido: str,
    region_sigungu: str,
) -> Optional[Set[str]]:
    
    # 나이/지역 필터가 모두 없는 경우 None 반환 (모든 정책 허용)
    if age is None and not region_sido and not region_sigungu:
        return None

    allowed: Set[str] = set()
    for policy_id, policy_meta in metadata.items():
        if _policy_passes_filters(
            policy_meta=policy_meta,
            age=age,
            region_sido=region_sido,
            region_sigungu=region_sigungu,
        ):
            allowed.add(str(policy_id))
    return allowed


def run_retrieval(args: argparse.Namespace) -> Dict[str, Any]:

    """
    - query: 질의 문자열
    - results: 검색 결과 리스트
    - debug: 가중치/필터 관련 진단 정보
    """

    load_dotenv()
    api_key = os.getenv(args.api_key_env, "").strip()
    if not api_key:
        raise EnvironmentError(f"{args.api_key_env} 환경변수가 비어 있습니다.")

    if not args.index.exists():
        raise FileNotFoundError(f"인덱스 파일이 없습니다: {args.index}")
    if not args.mapping.exists():
        raise FileNotFoundError(f"매핑 파일이 없습니다: {args.mapping}")
    if not args.chunks.exists():
        raise FileNotFoundError(f"청크 파일이 없습니다: {args.chunks}")
    if (args.age >= 0 or args.region_sido.strip() or args.region_sigungu.strip()) and not args.metadata.exists():
        raise FileNotFoundError(f"메타데이터 파일이 없습니다: {args.metadata}")

    # index-log에서 metric/model 설정을 읽고
    # query-model을 CLI에서 직접 주면 그 값을 우선시 함
    index_log = read_json(args.index_log) if args.index_log.exists() else {}
    query_model = args.query_model or index_log.get("embedding_model") or "text-embedding-3-small"
    metric = index_log.get("metric", "cosine")
    base_section_weights = (
        {sec: 1.0 for sec in ALL_SECTIONS}
        if args.disable_section_weight
        else parse_section_weights(args.section_weights)
    )
    dynamic_section_weights = {sec: 1.0 for sec in ALL_SECTIONS}
    section_intent_scores = {sec: 0 for sec in ALL_SECTIONS}
    if not (args.disable_section_weight or args.disable_dynamic_section_weight):
        dynamic_section_weights, section_intent_scores = infer_dynamic_section_weights(args.query)
    effective_section_weights: Dict[str, float] = {}
    for sec in ALL_SECTIONS:
        effective_section_weights[sec] = round(
            float(base_section_weights.get(sec, 1.0)) * float(dynamic_section_weights.get(sec, 1.0)),
            4,
        )

    dynamic_category_weights = {cat: 1.0 for cat in ALL_CATEGORIES}
    category_intent_scores = {cat: 0 for cat in ALL_CATEGORIES}
    if not args.disable_dynamic_category_weight:
        dynamic_category_weights, category_intent_scores = infer_dynamic_category_weights(args.query)

    index = faiss.read_index(str(args.index))
    mapping_rows = read_jsonl(args.mapping)
    chunk_map = build_chunk_map(read_jsonl(args.chunks))
    metadata = read_json(args.metadata) if args.metadata.exists() else {}

    age = None if args.age < 0 else int(args.age)
    region_sido = args.region_sido.strip()
    region_sigungu = args.region_sigungu.strip()
    allowed_policy_ids = build_allowed_policy_ids(
        metadata=metadata,
        age=age,
        region_sido=region_sido,
        region_sigungu=region_sigungu,
    )

    mapping_by_idx: Dict[int, Dict[str, Any]] = {}
    for row in mapping_rows:
        v = row.get("vector_idx")
        if v is None:
            continue
        mapping_by_idx[int(v)] = row

    # search-k는 1차 후보 크기
    # top-k보다 크게 잡아서 좋은 후보가 누락되지 않도록 함
    search_k = args.search_k if args.search_k > 0 else max(args.top_k * 8, args.top_k)
    if allowed_policy_ids is not None:
        # 필터 적용 시 후보가 줄어드므로 기본 후보폭을 넓힘
        search_k = max(search_k, args.top_k * 20)
    search_k = min(search_k, len(mapping_by_idx))

    # 질의 임베딩 생성
    client = OpenAI(api_key=api_key)
    q = embed_query(client, query_model, args.query)

    # 인덱스가 코사인 기준이면 query도 동일하게 정규화
    if metric == "cosine":
        q = normalize(q)
    q = q.reshape(1, -1).astype(np.float32)

    # FAISS 검색 : distances(점수), indices(vector_idx) 반환
    distances, indices = index.search(q, search_k)

    # vector_idx를 읽을 수 있는 결과로 복원
    results: List[Dict[str, Any]] = []
    seen_chunk_ids: Set[str] = set()
    seen_text_keys: Set[str] = set()
    dedup_skipped = 0

    for score, vidx in zip(distances[0].tolist(), indices[0].tolist()):
        if vidx < 0:
            continue
        row = mapping_by_idx.get(int(vidx))
        if not row:
            continue
        if allowed_policy_ids is not None and str(row.get("policy_id")) not in allowed_policy_ids:
            continue
        chunk_id = str(row.get("chunk_id"))
        if chunk_id in seen_chunk_ids:
            dedup_skipped += 1
            continue

        chunk = chunk_map.get(chunk_id, {})
        text = str(chunk.get("text", ""))
        text_key = ""
        if not args.disable_text_dedup:
            text_key = build_text_key(text, min_len=max(1, args.text_dedup_min_len))
            if text_key and text_key in seen_text_keys:
                dedup_skipped += 1
                continue

        seen_chunk_ids.add(chunk_id)
        if text_key:
            seen_text_keys.add(text_key)

        results.append(
            {
                "score": float(score),
                "vector_idx": int(vidx),
                "policy_id": row.get("policy_id"),
                "chunk_id": row.get("chunk_id"),
                "section": row.get("section"),
                "title": row.get("title"),
                "category": row.get("category"),
                "text_preview": text[: args.preview_chars].strip(),
                "text": text,
            }
        )

    # 섹션 가중치 반영 재정렬
    for r in results:
        r["rank_score"] = compute_rank_score(
            raw_score=float(r["score"]),
            metric=metric,
            section=str(r.get("section") or ""),
            section_weights=effective_section_weights,
            category=str(r.get("category") or ""),
            category_weights=dynamic_category_weights,
        )
        r["section_weight"] = effective_section_weights.get(str(r.get("section") or "").upper(), 1.0)
        r["category_weight"] = dynamic_category_weights.get(str(r.get("category") or "").lower(), 1.0)
    results.sort(key=lambda x: float(x["rank_score"]), reverse=True)
    results = results[: args.top_k]

    debug: Dict[str, Any] = {
        "query_model": query_model,
        "metric": metric,
        "base_section_weights": base_section_weights,
        "section_intent_scores": section_intent_scores,
        "dynamic_section_weights": dynamic_section_weights,
        "effective_section_weights": effective_section_weights,
        "category_intent_scores": category_intent_scores,
        "dynamic_category_weights": dynamic_category_weights,
        "age": age,
        "region_sido": region_sido,
        "region_sigungu": region_sigungu,
        "allowed_policy_ids_count": None if allowed_policy_ids is None else len(allowed_policy_ids),
        "dedup_skipped": dedup_skipped,
        "result_count": len(results),
    }
    return {"query": args.query, "results": results, "debug": debug}


def main() -> None:
    args = parse_args()
    payload = run_retrieval(args)
    results: List[Dict[str, Any]] = payload["results"]
    debug: Dict[str, Any] = payload["debug"]

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    print(f"[query] {args.query}")
    # print(f"[model] {debug['query_model']}")
    # print(f"[metric] {debug['metric']}")
    if not args.disable_dynamic_section_weight and not args.disable_section_weight:
        print(f"[section_intent_scores] {debug['section_intent_scores']}")
        print(f"[dynamic_section_weights] {debug['dynamic_section_weights']}")
    print(f"[effective_section_weights] {debug['effective_section_weights']}")
    if not args.disable_dynamic_category_weight:
        print(f"[category_intent_scores] {debug['category_intent_scores']}")
        print(f"[dynamic_category_weights] {debug['dynamic_category_weights']}")
    if debug["allowed_policy_ids_count"] is not None:
        print(
            "[filter]"
            f" age= {debug['age'] if debug['age'] is not None else '-'}"
            f", region(시/도)= {debug['region_sido'] or '-'}"
            f", region(시/군/구)= {debug['region_sigungu'] or '-'}"
            f", allowed_policies= {debug['allowed_policy_ids_count']}"
        )
    print(f"[dedup_skipped] {debug['dedup_skipped']}")
    print(f"[result_count] {debug['result_count']}")
    for i, r in enumerate(results, start=1):
        print("-" * 80)
        print(
            f"{i}. score={r['score']:.4f} rank={r['rank_score']:.4f} "
            f"sec_w={r['section_weight']:.3f} cat_w={r['category_weight']:.3f} "
            f"policy_id={r['policy_id']} "
            f"chunk_id={r['chunk_id']} section={r['section']}"
        )
        print(f"정책명: {r['title']}")
        print(r["text_preview"])


if __name__ == "__main__":
    main()