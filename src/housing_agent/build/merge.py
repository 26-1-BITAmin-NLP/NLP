# 데이터 정규화 코드 병합 후 전처리된 최종 데이터 파일 생성
import json
from pathlib import Path
from typing import Any, Dict, List

from src.housing_agent.normalize.finance import normalize_finance
from src.housing_agent.normalize.housing_supply import normalize_housing_supply
from src.housing_agent.normalize.housing_cost_etc import normalize_housing_cost_etc
from src.housing_agent.normalize.dormitory import normalize_dormitory

ROOT = Path(__file__).resolve().parents[3]

DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"

OUT_PATH = DATA_PROCESSED / "policies.json"

FILES = {
    "finance": "금융지원_all.json",
    "housing_supply": "주택공급_all.json",
    "housing_cost_etc": "주거비_기타지원_all.json",
    "dormitory": "기숙사_all.json",
}


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def assert_unique_policy_ids(policies: List[Dict[str, Any]]) -> None:
    seen = {}
    dups = []
    for p in policies:
        pid = p.get("policy_id")
        if pid in seen:
            dups.append((pid, seen[pid].get("title"), p.get("title")))
        else:
            seen[pid] = p
    if dups:
        # 중복 일부만 표시
        preview = "\n".join([f"- {pid}: {t1} / {t2}" for pid, t1, t2 in dups[:10]])
        raise ValueError(f"Duplicate policy_id detected (showing up to 10):\n{preview}")


def quick_sanity_print(policies: List[Dict[str, Any]], n: int = 5) -> None:
    print(f"\n[SANITY] total={len(policies)}")
    for p in policies[:n]:
        print("-" * 60)
        print(f"title: {p.get('title')}")
        print(f"category: {p.get('category')}")
        rt = p.get("raw_text") or ""
        print(f"raw_text_preview: {rt[:300].replace(chr(10), ' ')}")
    print("-" * 60 + "\n")


def main() -> None:
    # raw 데이터 로드
    finance_raw = load_json(DATA_RAW / FILES["finance"])
    supply_raw = load_json(DATA_RAW / FILES["housing_supply"])
    cost_raw = load_json(DATA_RAW / FILES["housing_cost_etc"])
    dorm_raw = load_json(DATA_RAW / FILES["dormitory"])

    # 각 카테고리 별로 데이터 정규화
    normalized: List[Dict[str, Any]] = []
    normalized += [normalize_finance(x) for x in finance_raw]
    normalized += [normalize_housing_supply(x) for x in supply_raw]
    normalized += [normalize_housing_cost_etc(x) for x in cost_raw]

    # 기숙사 데이터는 그룹핑 먼저 진행
    normalized += normalize_dormitory(dorm_raw)

    # 최소 검증
    assert_unique_policy_ids(normalized)

    # raw_text 빈 값 체크
    empty_rt = [p for p in normalized if not (p.get("raw_text") or "").strip()]
    if empty_rt:
        raise ValueError(f"Found empty raw_text policies: {len(empty_rt)} (e.g. {empty_rt[0].get('policy_id')})")

    # 전처리 파일 저장
    save_json(OUT_PATH, normalized)
    print(f"[OK] saved to: {OUT_PATH}")

    # 데이터 출력 확인
    quick_sanity_print(normalized, n=5)


if __name__ == "__main__":
    main()