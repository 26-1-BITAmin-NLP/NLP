from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
import faiss

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_VECTOR_PATH = ROOT / "data" / "vectorstore" / "policies_v2_embeddings.npy"
DEFAULT_MAPPING_PATH = ROOT / "data" / "vectorstore" / "policies_v2_embedding_mapping.jsonl"
DEFAULT_EMBED_LOG_PATH = ROOT / "data" / "vectorstore" / "policies_v2_embedding_log.json"
DEFAULT_INDEX_PATH = ROOT / "data" / "vectorstore" / "policies_v2_index.faiss"
DEFAULT_INDEX_INFO_PATH = ROOT / "data" / "vectorstore" / "policies_v2_index_log.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FAISS 인덱스 생성")
    parser.add_argument("--vectors", type=Path, default=DEFAULT_VECTOR_PATH, help="임베딩 npy 경로")
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING_PATH, help="vector 매핑 jsonl")
    parser.add_argument("--embed-log", type=Path, default=DEFAULT_EMBED_LOG_PATH, help="임베딩 로그 json")
    parser.add_argument("--out-index", type=Path, default=DEFAULT_INDEX_PATH, help="FAISS 인덱스 출력 경로")
    parser.add_argument("--out-info", type=Path, default=DEFAULT_INDEX_INFO_PATH, help="인덱스 정보 json")
    parser.add_argument(
        "--metric",
        type=str,
        choices=["cosine", "l2"],
        default="cosine",
        help="검색 거리 기준",
    )
    return parser.parse_args()


def count_jsonl_rows(path: Path) -> int:
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def load_json_if_exists(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_rows(mat: np.ndarray) -> np.ndarray:
    # cosine 검색을 위해 각 벡터에 대해 L2 정규화 진행
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def main() -> None:
    args = parse_args()

    if not args.vectors.exists():
        raise FileNotFoundError(f"벡터 파일이 없습니다: {args.vectors}")
    if not args.mapping.exists():
        raise FileNotFoundError(f"매핑 파일이 없습니다: {args.mapping}")

    matrix = np.load(args.vectors)
    if matrix.ndim != 2:
        raise ValueError(f"벡터 shape이 2차원이 아닙니다: {matrix.shape}")
    if matrix.shape[0] == 0:
        raise ValueError("벡터가 비어 있습니다.")

    matrix = np.asarray(matrix, dtype=np.float32, order="C")
    num_vectors, dim = matrix.shape

    mapping_count = count_jsonl_rows(args.mapping)
    if mapping_count != num_vectors:
        raise ValueError(
            f"벡터 수({num_vectors})와 매핑 행 수({mapping_count})가 다릅니다. "
            "임베딩 산출물을 다시 맞춰주세요."
        )

    normalized = False
    if args.metric == "cosine":
        matrix = normalize_rows(matrix)
        index = faiss.IndexFlatIP(dim)
        normalized = True
    else:
        index = faiss.IndexFlatL2(dim)

    index.add(matrix)

    args.out_index.parent.mkdir(parents=True, exist_ok=True)
    args.out_info.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(args.out_index))

    embed_log = load_json_if_exists(args.embed_log)
    info = {
        "index_type": type(index).__name__,
        "metric": args.metric,
        "normalized_vectors": normalized,
        "num_vectors": int(num_vectors),
        "dimension": int(dim),
        "index_path": str(args.out_index),
        "vectors_path": str(args.vectors),
        "mapping_path": str(args.mapping),
        "embedding_model": embed_log.get("model"),
    }
    with open(args.out_info, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    print(f"[done] faiss_index: {args.out_index}")
    print(f"[done] index_info: {args.out_info}")


if __name__ == "__main__":
    main()
