import json
import os
import re
from pathlib import Path

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
                "dcls_strt_day": base["dcls_strt_day"]
            })

    return products

# 통합 리스트 저장
def save_processed_json(products: list, filename: str):
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


# 상품 리스트 하나로 합쳐서 정리
def parse_all_products() -> list:
    # 프로젝트 루트 기준 data 폴더 사용 (실제 위치: /data/raw, /data/processed)
    project_root = Path(__file__).resolve().parents[2]
    raw_dir = project_root / "data" / "raw"
    processed_dir = project_root / "data" / "processed"

    deposit_data = load_raw_json(str(raw_dir / "deposit.json"))
    saving_data = load_raw_json(str(raw_dir / "saving.json"))
    rentloan_data = load_raw_json(str(raw_dir / "rentloan.json"))

    products = []
    products += parse_deposit_products(deposit_data)
    products += parse_saving_products(saving_data)
    products += parse_rentloan_products(rentloan_data)

    save_processed_json(
        products,
        str(processed_dir / "products.json")
    )

    return products

# 상품 데이터 정리 실행
products = parse_all_products()

# =================
# 사용자 조건 필터링
# =================
def filter(products: list, user_conditions: dict) -> list:
    """
    사용자 입력값을 바탕으로 가입 불가능한 상품(성별, 나이, 주거형태 등)을 필터링
    """
    filtered = []
    
    # 사용자 입력값 추출
    age = user_conditions.get("age", 25)
    rent_type = user_conditions.get("rent_type", "상관없음")
    gender = user_conditions.get("gender", "기타")
    
    for prod in products:
        join_member = prod.get("join_member", "")
        prod_type = prod.get("type", "")
        
        # 1. 주거 형태(월세 희망 시 전세자금대출 pass)
        if rent_type == "월세" and prod_type == "rentloan":
            continue
            
        # 2. 성별
        # 상품 가입 대상이 '여성' -> 남성 제외
        if "여성" in join_member and gender == "남성":
            continue
        # 상품 가입 대상이 '남성' -> 여성 제외
        if "남성" in join_member and gender == "여성":
            continue
            
        # 3. 나이
        min_age = 0
        max_age = 999
        
        # "만19세~만34세" 같은 범위형 텍스트 추출
        range_match = re.search(r'(?:만\s*)?(\d+)세\s*~\s*(?:만\s*)?(\d+)세', join_member)
        if range_match:
            min_age = int(range_match.group(1))
            max_age = int(range_match.group(2))
        else:
            # "만 17세 이상", "14세이상" 같은 하한선 텍스트 추출
            min_match = re.search(r'(?:만\s*)?(\d+)세\s*이상', join_member)
            if min_match:
                min_age = int(min_match.group(1))
                
            # "15세 이하", "만 34세 이하" 같은 상한선 텍스트 추출
            max_match = re.search(r'(?:만\s*)?(\d+)세\s*이하', join_member)
            if max_match:
                max_age = int(max_match.group(1))

        # 파싱된 나이 조건과 사용자의 나이 대조
        if age < min_age or age > max_age:
            continue

        # 조건들을 모두 통과한 상품만 추가
        filtered.append(prod)
        
    return filtered
