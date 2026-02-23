from processing import parse_all_products, filter
from llm import scoring_and_report
import os
import json

def main():

    # 상품 데이터 불러오기
    base_dir = os.path.dirname(__file__)
    json_path = os.path.join(base_dir, "data", "processed", "products.json")
    
    with open(json_path, "r", encoding="utf-8") as f:
        products = json.load(f)

    print(f"{json_path} 파일에서 상품 데이터 불러오기 완료")  
    
    # 사용자 조건 필터링
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
        "preferred_banks": ["주식회사 카카오뱅크", "우리은행"] 
    }
    
    filtered = filter(products, user_conditions)
    print(f"필터링 완료: 총 {len(filtered)}개의 상품 통과")

    # 스코어링, LLM 의견서 생성
    finance_top3, finance_report = scoring_and_report(filtered, user_conditions)
    print(f"스코어링 및 의견서 생성 완료\n")
    print(finance_report)

if __name__ == "__main__":
    main()
