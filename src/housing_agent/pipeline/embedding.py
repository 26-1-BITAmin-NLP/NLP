from __future__ import annotations

"""
입력
- chunking 단계에서 만든 policies_v2_chunked.jsonl 파일

출력
- .npy : 임베딩 벡터 행렬
- manifest.jsonl: vector_idx -> 원본 chunk 메타 매핑
- meta.json: 디버깅용, 기록 저장
"""

import argparse
import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List
from openai import OpenAI
from dotenv import load_dotenv

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = ROOT / "data" / "processed" / "policies_v2_chunked.jsonl"
DEFAULT_OUT_DIR = ROOT / "data" / "vectorstore"
DEFAULT_VEC_PATH = DEFAULT_OUT_DIR / "policies_v2_embeddings.npy"
DEFAULT_MANIFEST_PATH = DEFAULT_OUT_DIR / "policies_v2_embedding_mapping.jsonl"
DEFAULT_META_PATH = DEFAULT_OUT_DIR / "policies_v2_embedding_log.json"

# 임베딩 파싱 코드
# OpenAI API를 사용하여 텍스트 청크를 벡터로 변환

def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(description="OpenAI 임베딩 생성 스크립트")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="chunked jsonl 파일")
    parser.add_argument("--out-vectors", type=Path, default=DEFAULT_VEC_PATH, help="임베딩 벡터 npy")
    parser.add_argument(
        "--out-manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="벡터 인덱스-청크 매핑 jsonl",
    )
    parser.add_argument("--out-meta", type=Path, default=DEFAULT_META_PATH, help="임베딩 메타 json")
    parser.add_argument(
        "--model",
        type=str,
        default="text-embedding-3-small",
        help="OpenAI 임베딩 모델명",
    )
    parser.add_argument("--batch-size", type=int, default=32, help="배치 크기")
    parser.add_argument("--max-retries", type=int, default=5, help="API 재시도 횟수")
    parser.add_argument("--sleep-base", type=float, default=1.2, help="재시도 기본 대기(초)")
    parser.add_argument("--limit", type=int, default=0, help="상위 N개 청크만 처리(0이면 전체)")
    parser.add_argument(
        "--api-key-env",
        type=str,
        default="OPENAI_API_KEY",
        help="OpenAI API Key 환경변수명",
    )
    parser.add_argument(
        "--skip-empty-text",
        action="store_true",
        help="빈 text 청크 제외",
    )
    return parser.parse_args()

# jsonl 파일을 한 줄씩 읽어서 dict 리스트로 반환
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

# 리스트를 고정 크기 청크로 분할
def chunked(items: List[Dict[str, Any]], size: int) -> Iterable[List[Dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def embed_batch(
    client: OpenAI,
    texts: List[str],
    model: str,
    max_retries: int,
    sleep_base: float,
) -> List[List[float]]:
    
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = client.embeddings.create(model=model, input=texts)
            return [row.embedding for row in resp.data]
        except Exception as exc:
            last_error = exc
            if attempt == max_retries - 1:
                break
            jitter = random.uniform(0, 0.4)
            sleep_sec = (sleep_base * (2**attempt)) + jitter
            print(f"embedding 실패: {sleep_sec:.2f}s 대기 후 재시도 ({attempt + 1}/{max_retries})")
            time.sleep(sleep_sec)
    raise RuntimeError(f"API 호출 실패: {last_error}")


def build_manifest_row(row: Dict[str, Any], vector_idx: int) -> Dict[str, Any]:

    return {
        "vector_idx": vector_idx,
        "chunk_id": row.get("chunk_id"),
        "policy_id": row.get("policy_id"),
        "category": row.get("category"),
        "title": row.get("title"),
        "section": row.get("section"),
    }


def main() -> None:
    args = parse_args()

    if load_dotenv is not None:
        load_dotenv()

    if not args.input.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {args.input}")
    if args.batch_size <= 0:
        raise ValueError("--batch-size는 1 이상이어야 합니다.")

    api_key = os.getenv(args.api_key_env, "").strip()
    if not api_key:
        raise EnvironmentError(f"{args.api_key_env} 환경변수가 비어 있습니다.")

    # 청크 로드 및 선택적 필터링
    rows = read_jsonl(args.input)
    if args.skip_empty_text:
        rows = [r for r in rows if str(r.get("text", "")).strip()]
    if args.limit > 0:
        rows = rows[: args.limit]
    if not rows:
        raise ValueError("처리할 청크가 없습니다.")

    client = OpenAI(api_key=api_key)

    vectors: List[List[float]] = []
    manifest: List[Dict[str, Any]] = []

    total = len(rows)
    done = 0

    # 청크 단위 임베딩 생성
    for batch_rows in chunked(rows, args.batch_size):
        texts = [str(r.get("text", "")) for r in batch_rows]
        emb = embed_batch(
            client=client,
            texts=texts,
            model=args.model,
            max_retries=args.max_retries,
            sleep_base=args.sleep_base,
        )
        if len(emb) != len(batch_rows):
            raise RuntimeError("임베딩 결과 개수가 입력 배치 개수와 다릅니다.")

        for row, vector in zip(batch_rows, emb):
            vector_idx = len(vectors)
            vectors.append(vector)
            manifest.append(build_manifest_row(row, vector_idx))

        done += len(batch_rows)
        print(f"[progress] {done}/{total} embedded")

    matrix = np.asarray(vectors, dtype=np.float32)

    args.out_vectors.parent.mkdir(parents=True, exist_ok=True)
    args.out_manifest.parent.mkdir(parents=True, exist_ok=True)
    args.out_meta.parent.mkdir(parents=True, exist_ok=True)

    # 임베딩 벡터 파일
    np.save(args.out_vectors, matrix)

    # 역매핑(manifest) 파일
    with open(args.out_manifest, "w", encoding="utf-8") as f:
        for row in manifest:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # 실행 요약(meta) 파일
    meta = {
        "model": args.model,
        "input_path": str(args.input),
        "num_vectors": int(matrix.shape[0]),
        "dimension": int(matrix.shape[1]),
        "dtype": str(matrix.dtype),
        "batch_size": args.batch_size,
        "vectors_path": str(args.out_vectors),
        "manifest_path": str(args.out_manifest),
    }
    with open(args.out_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"[done] vectors: {args.out_vectors}")
    print(f"[done] mapping: {args.out_manifest}")
    print(f"[done] log: {args.out_meta}")


if __name__ == "__main__":
    main()
