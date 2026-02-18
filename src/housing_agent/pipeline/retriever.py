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
from typing import Any, Dict, List

import faiss
from openai import OpenAI

import numpy as np
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INDEX_PATH = ROOT / "data" / "vectorstore" / "policies_v2_index.faiss"
DEFAULT_INDEX_LOG_PATH = ROOT / "data" / "vectorstore" / "policies_v2_index_log.json"
DEFAULT_MAPPING_PATH = ROOT / "data" / "vectorstore" / "policies_v2_embedding_mapping.jsonl"
DEFAULT_CHUNK_PATH = ROOT / "data" / "processed" / "policies_v2_chunked.jsonl"


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
    parser.add_argument("--preview-chars", type=int, default=260, help="본문 미리보기 글자 수")
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

    # index-log에서 metric/model 설정을 읽고
    # query-model을 CLI에서 직접 주면 그 값을 우선시 함
    index_log = read_json(args.index_log) if args.index_log.exists() else {}
    query_model = args.query_model or index_log.get("embedding_model") or "text-embedding-3-small"
    metric = index_log.get("metric", "cosine")

    index = faiss.read_index(str(args.index))
    mapping_rows = read_jsonl(args.mapping)
    chunk_map = build_chunk_map(read_jsonl(args.chunks))

    mapping_by_idx: Dict[int, Dict[str, Any]] = {}
    for row in mapping_rows:
        v = row.get("vector_idx")
        if v is None:
            continue
        mapping_by_idx[int(v)] = row

    # search-k는 1차 후보 크기
    # top-k보다 크게 잡아서 좋은 후보가 누락되지 않도록 함
    search_k = args.search_k if args.search_k > 0 else max(args.top_k * 8, args.top_k)
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
