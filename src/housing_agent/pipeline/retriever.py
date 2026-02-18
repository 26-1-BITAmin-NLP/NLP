from __future__ import annotations

"""

입력
- 사용자 질의 문자열
- FAISS 인덱스
- vector_idx, chunk 메타 매핑
- 원본 청크 텍스트

출력
- 유사도 상위 k개 청크 (점수, policy_id, chunk_id, 미리보기 텍스트)

"""

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import faiss
from openai import OpenAI

import numpy as np
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INDEX_PATH = ROOT / "data" / "vectorstore" / "policies_v2_index.faiss"
DEFAULT_INDEX_LOG_PATH = ROOT / "data" / "vectorstore" / "policies_v2_index_log.json"
DEFAULT_MAPPING_PATH = ROOT / "data" / "vectorstore" / "policies_v2_embedding_mapping.jsonl"
DEFAULT_CHUNK_PATH = ROOT / "data" / "processed" / "policies_v2_chunked.jsonl"
DEFAULT_METADATA_PATH = ROOT / "data" / "processed" / "policies_v2_metadata.json" # 정책 단위 metadata 결합


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


def main() -> None:
    args = parse_args()

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
    for score, vidx in zip(distances[0].tolist(), indices[0].tolist()):
        if vidx < 0:
            continue
        row = mapping_by_idx.get(int(vidx))
        if not row:
            continue
        if allowed_policy_ids is not None and str(row.get("policy_id")) not in allowed_policy_ids:
            continue
        chunk = chunk_map.get(str(row.get("chunk_id")), {})
        text = str(chunk.get("text", ""))
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
        if len(results) >= args.top_k:
            break

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    print(f"[query] {args.query}")
    # print(f"[model] {query_model}")
    # print(f"[metric] {metric}")
    if allowed_policy_ids is not None:
        print(
            "[filter]"
            f" age= {age if age is not None else '-'}"
            f", region(시/도)= {region_sido or '-'}"
            f", region(시/군/구)= {region_sigungu or '-'}"
            f", allowed_policies= {len(allowed_policy_ids)}"
        )
    print(f"[result_count] {len(results)}")
    for i, r in enumerate(results, start=1):
        print("-" * 80)
        print(
            f"{i}. score={r['score']:.4f} policy_id={r['policy_id']} "
            f"chunk_id={r['chunk_id']} section={r['section']}"
        )
        print(f"정책명: {r['title']}")
        print(r["text_preview"])


if __name__ == "__main__":
    main()