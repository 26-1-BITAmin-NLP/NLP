import json
import os

# =================
# 상품 데이터 정리
# =================

# 데이터 읽어와서 dict 형태로 변환
def load_raw_json(filepath: str) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

# 정기예금 데이터
# 상품 row 형태 정리
def parse_deposit_products(data: dict) -> list:
    base_list = data["baseList"]
    option_list = data["optionList"]

    products = []

    for base in base_list:
        fin_prdt_cd = base["fin_prdt_cd"]

        matched_options = [
            opt for opt in option_list
            if opt["fin_prdt_cd"] == fin_prdt_cd
        ]

        for opt in matched_options:
            products.append({
                "type": "deposit",
                "bank": base["kor_co_nm"],
                "name": base["fin_prdt_nm"],
                "term": int(opt["save_trm"]),
                "base_rate": float(opt["intr_rate"] or 0),
                "max_rate": float(opt["intr_rate2"] or 0),
                "join_deny": base["join_deny"],
                "join_member": base["join_member"],
                "join_way": base["join_way"],
                "spcl_cnd": base["spcl_cnd"],
                "max_limit": base.get("max_limit"),
                "dcls_strt_day": base["dcls_strt_day"]
            })

    return products

# 적금 데이터
# 상품 row 형태 정리
def parse_saving_products(data: dict) -> list:
    base_list = data["baseList"]
    option_list = data["optionList"]

    products = []

    for base in base_list:
        fin_prdt_cd = base["fin_prdt_cd"]

        matched_options = [
            opt for opt in option_list
            if opt["fin_prdt_cd"] == fin_prdt_cd
        ]

        for opt in matched_options:
            products.append({
                "type": "saving",
                "bank": base["kor_co_nm"],
                "name": base["fin_prdt_nm"],
                "term": int(opt["save_trm"]),
                "base_rate": float(opt["intr_rate"] or 0),
                "max_rate": float(opt["intr_rate2"] or 0),
                "join_deny": base["join_deny"],
                "join_member": base["join_member"],
                "join_way": base["join_way"],
                "spcl_cnd": base["spcl_cnd"],
                "max_limit": base.get("max_limit"),
                "dcls_strt_day": base["dcls_strt_day"]
            })

    return products

# 전세자금대출 데이터
# 상품 row 형태 정리
def parse_rentloan_products(data: dict) -> list:
    base_list = data["baseList"]
    option_list = data["optionList"]

    products = []

    for base in base_list:
        fin_prdt_cd = base["fin_prdt_cd"]

        matched_options = [
            opt for opt in option_list
            if opt["fin_prdt_cd"] == fin_prdt_cd
        ]

        for opt in matched_options:
            products.append({
                "type": "rentloan",
                "bank": base["kor_co_nm"],
                "name": base["fin_prdt_nm"],
                "min_rate": float(opt["lend_rate_min"] or 0),
                "max_rate": float(opt["lend_rate_max"] or 0),
                "repay_type": opt["rpay_type_nm"],
                "loan_lmt": base.get("loan_lmt"),
                "spcl_cnd": base.get("spcl_cnd"),
                "etc_note": base.get("etc_note"),
                "dcls_strt_day": base["dcls_strt_day"]
            })

    return products

# 통합 리스트 저장
def save_processed_json(products: list, filename: str):
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


# 상품 리스트 하나로 합쳐서 정리!!
def parse_all_products() -> list:
    base_dir = os.path.dirname(__file__)

    raw_dir = os.path.join(base_dir, "api_data", "raw")
    processed_dir = os.path.join(base_dir, "api_data", "processed")

    deposit_data = load_raw_json(os.path.join(raw_dir, "deposit.json"))
    saving_data = load_raw_json(os.path.join(raw_dir, "saving.json"))
    rentloan_data = load_raw_json(os.path.join(raw_dir, "rentloan.json"))

    products = []
    products += parse_deposit_products(deposit_data)
    products += parse_saving_products(saving_data)
    products += parse_rentloan_products(rentloan_data)

    save_processed_json(
        products,
        os.path.join(processed_dir, "products.json")
    )

    return products

# 상품 데이터 정리 실행
products = parse_all_products()

# =================
# 사용자 조건 필터링
# =================
def filter(products, user_condition):
    filtered = []

    return filtered