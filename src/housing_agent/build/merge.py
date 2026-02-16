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
        preview = "\n".join([f"- {pid}: {t1} / {t2}" for pid, t1, t2 in dups[:10]])
        raise ValueError(f"Duplicate policy_id detected: \n{preview}")

def preview_print(policies: List[Dict[str, Any]], n: int = 5) -> None:
    print(f"\ntotal= {len(policies)}")
    for p in policies[:n]:
        print("-" * 60)
        print(f"title: {p.get('title')}")
        print(f"category: {p.get('category')}")
        et = (p.get("eligibility_text") or "")[:200].replace(chr(10), " ")
        bt = (p.get("benefit_text") or "")[:200].replace(chr(10), " ")
        pt = (p.get("process_text") or "")[:200].replace(chr(10), " ")
        print(f"eligibility_text: {et}")
        print(f"benefit_text: {bt}")
        print(f"process_text: {pt}")
    print("-" * 60 + "\n")

def main() -> None:
    finance_raw = load_json(DATA_RAW / FILES["finance"])
    supply_raw = load_json(DATA_RAW / FILES["housing_supply"])
    cost_raw = load_json(DATA_RAW / FILES["housing_cost_etc"])
    dorm_raw = load_json(DATA_RAW / FILES["dormitory"])

    finance_raw = sorted(finance_raw, key=lambda x: x.get("policy_name", ""))
    supply_raw = sorted(supply_raw, key=lambda x: x.get("policy_name", ""))
    cost_raw = sorted(cost_raw, key=lambda x: x.get("policy_title", ""))

    normalized: List[Dict[str, Any]] = []
    normalized += [normalize_finance(x) for x in finance_raw]
    normalized += [normalize_housing_supply(x, idx) for idx, x in enumerate(supply_raw, start=1)]
    normalized += [normalize_housing_cost_etc(x, idx) for idx, x in enumerate(cost_raw, start=1)]
    normalized += normalize_dormitory(dorm_raw)

    assert_unique_policy_ids(normalized)

    # 텍스트가 전부 비어있는 정책은 오류로 간주
    empty_core = [
        p for p in normalized
        if not (p.get("eligibility_text") or "").strip()
        and not (p.get("benefit_text") or "").strip()
        and not (p.get("process_text") or "").strip()
    ]
    if empty_core:
        raise ValueError(f"Found empty text policies: {len(empty_core)} (e.g. {empty_core[0].get('policy_id')})")

    save_json(OUT_PATH, normalized)
    print(f"[OK] saved to: {OUT_PATH} / count={len(normalized)}")

    preview_print(normalized, n=5)

if __name__ == "__main__":
    main()
