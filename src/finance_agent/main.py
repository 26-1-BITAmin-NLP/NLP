import os
import json
from typing import Dict, Any, Tuple, List

# Import strategy:
# - When used as a package: from .processing / .llm
# - When executed directly: fallback to absolute import
try:
    from .processing import filter as finance_filter
    from .llm import scoring_and_report
except ImportError:
    from processing import filter as finance_filter
    from llm import scoring_and_report


def _load_products() -> List[dict]:
    """Load products from finance_agent/data/processed/products.json safely."""
    base_dir = os.path.dirname(__file__)
    json_path = os.path.join(base_dir, "data", "processed", "products.json")

    if not os.path.exists(json_path):
        raise FileNotFoundError(
            f"products.json not found: {json_path}\n"
            f"Expected path: src/finance_agent/data/processed/products.json"
        )

    with open(json_path, "r", encoding="utf-8") as f:
        products = json.load(f)

    return products


def run_finance(user_conditions: Dict[str, Any]) -> Dict[str, Any]:
    """
    Streamlit에서 호출할 금융 진입점.
    입력: user_conditions (dict)
    출력: finance_memo (dict)  # PDF/화면에 그대로 출력 가능한 구조
    """
    products = _load_products()

    # 1) 필터링
    filtered = finance_filter(products, user_conditions)

    # 2) 스코어링 + LLM 의견서 생성
    # scoring_and_report가 (finance_top3, finance_memo)를 반환한다는 기존 로직 유지
    finance_top3, finance_memo = scoring_and_report(filtered, user_conditions)

    # 데모 안정성: finance_memo 필수 키가 없으면 최소 형태로 보정
    if not isinstance(finance_memo, dict):
        raise ValueError("finance_memo must be a dict.")

    finance_memo.setdefault("summary", "")
    finance_memo.setdefault("recommended_products", finance_top3 if isinstance(finance_top3, list) else [])
    finance_memo.setdefault("asset_strategy", "")

    return finance_memo


def main() -> None:
    """CLI 테스트용 엔트리(기존 유지)."""
    user_conditions = {
        "age": 25,
        "gender": "남성",
        "household_type": "청년(1인가구)",
        "region": {"city": "서울특별시", "gu": "관악구"},
        "monthly_income_m": 250,
        "assets_m": 500,
        "debt_m": 500,
        "rent_type": "월세",
        "move_timeline": "1~3개월",
        "monthly_housing_budget_m": 60,
        "risk_pref": "중립",
        "preferred_banks": ["주식회사 카카오뱅크", "우리은행"],
    }

    finance_memo = run_finance(user_conditions)
    print("스코어링 및 의견서 생성 완료\n")
    print("\"finance_memo\":", json.dumps(finance_memo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
    