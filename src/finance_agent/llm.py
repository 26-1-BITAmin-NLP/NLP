import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# API KEY 불러오기
load_dotenv()
API_KEY = os.getenv("OPEN_API_KEY")

# ===========================
# 상품 스코어링 => Top 10 추출
# ===========================
def get_quantitative_top10(filtered: list, user_conditions: dict) -> list:
    """
    파이썬 기반 스코어링
    금리, 선호 은행, 지역 친화도를 바탕으로 Top 10 추출
    """
    scored_products = []
    
    # 사용자 입력값 추출
    preferred_banks = user_conditions.get("preferred_banks", [])
    region_info = user_conditions.get("region", {})
    desired_city = region_info.get("city", "") 
    monthly_income = user_conditions.get("monthly_income_m", 0) 
    
    for prod in filtered:
        score = 0
        prod_type = prod.get("type", "")
        bank_name = prod.get("bank", "")
        
        # [1] 금리 (최대 50점)
        if prod_type in ["deposit", "saving"]:
            base_rate = float(prod.get("base_rate") or 0.0)
            max_rate = float(prod.get("max_rate") or base_rate)
            
            # 기본 금리가 높을수록 높은 점수
            score += min(base_rate * 10, 30)
            # 우대 금리 폭이 클수록 높은 점수
            score += min((max_rate - base_rate) * 10, 10)
            
        elif prod_type == "rentloan":
            min_rate = float(prod.get("min_rate") or 0.0)
            if min_rate > 0:
                # 대출은 최저금리가 낮을수록 유리 (2.0% 기준)
                score += max(0, 30 - ((min_rate - 2.0) * 10))
            score += 10 # 우대조건 계산의 복잡성을 고려해 기본 점수 부여
            
        # [2] 사용자 선호 은행 (최대 30점)
        if bank_name in preferred_banks:
            score += 30
            
        # [3] 지역 및 소득 친화도 (최대 30점)
        regional_banks = {
            "부산": ["부산은행"], 
            "경남": ["경남은행"], 
            "광주": ["광주은행"], 
            "전남": ["광주은행"], 
            "전북": ["전북은행"], 
            "제주": ["제주은행"], 
            "대구": ["아이엠뱅크"], 
            "경북": ["아이엠뱅크"]
        }
        
        for region_key, banks in regional_banks.items():
            if region_key in desired_city and bank_name in banks:
                score += 15
                break
                
        # 서민금융/저소득층 타겟 상품 매칭
        is_low_income_target = "서민" in prod.get("name", "") or "새희망" in prod.get("name", "")
        if is_low_income_target and monthly_income <= 300:
            score += 15
            
        prod["quant_score"] = round(score, 2)
        scored_products.append(prod)
        
    # 정량적 점수 내림차순 정렬 후 Top 10 반환
    scored_products.sort(key=lambda x: x["quant_score"], reverse=True)
    return scored_products[:10]

# =================================
# llm 사용 => Top3 선정, 의견서 작성
# =================================
def scoring_and_report(filtered: list, user_conditions: dict) -> tuple:
    """
    LLM 기반 스코어링
    Top 10 추출 후 LLM 분석을 거쳐 Top 3 반환
    """
    # 1. Top 10 후보군 추출
    top10_candidates = get_quantitative_top10(filtered, user_conditions)
    
    if not top10_candidates:
        return [], "조건에 맞는 상품을 찾을 수 없습니다. 조건을 조금 완화해 보세요."
        
    # OpenAI 클라이언트 세팅
    client = OpenAI(api_key= API_KEY)
    
    # 2. 사용자 입력값 문자열로 정리
    region = user_conditions.get("region", {})
    
    profile_text = f"""
    [필수 입력 정보]
    - 나이: {user_conditions.get('age', 0)}세
    - 성별: {user_conditions.get('gender', '미입력')}
    - 가구 유형: {user_conditions.get('household_type', '미입력')}
    - 거주 희망 지역: {region.get('city', '')} {region.get('gu', '')}
    - 월 소득: {user_conditions.get('monthly_income_m', 0)}만 원
    - 보유 자산: {user_conditions.get('assets_m', 0)}만 원
    - 주거 형태 선호: {user_conditions.get('rent_type', '미입력')}
    - 입주 희망 시점: {user_conditions.get('move_timeline', '미입력')}
    
    [선택 입력 정보]
    - 월 주거 예산: {user_conditions.get('monthly_housing_budget_m', 0)}만 원
    - 리스크 성향: {user_conditions.get('risk_pref', '미입력')}
    - 부채: {user_conditions.get('debt_m', 0)}만 원
    """

    candidates_text = ""
    for i, prod in enumerate(top10_candidates):
        candidates_text += f"\n[후보 {i+1}] {prod.get('bank')} - {prod.get('name')} (상품구분: {prod.get('type')})\n"
        if prod.get("type") in ["deposit", "saving"]:
            candidates_text += f"- 기본금리: {prod.get('base_rate', 0)}% / 최고우대금리: {prod.get('max_rate', 0)}%\n"
        else:
            candidates_text += f"- 최저금리: {prod.get('min_rate', 0)}% / 최고금리: {prod.get('max_rate', 0)}%\n"
        candidates_text += f"- 가입대상: {prod.get('join_member', '제한없음')}\n"
        candidates_text += f"- 우대조건(핵심): {prod.get('spcl_cnd', '없음')}\n"

    # 3. LLM 프롬프트 구성
    system_prompt = """
    당신은 고객의 생애 주기와 재무 상태를 분석하는 꼼꼼한 전문 금융 어드바이저입니다.
    시스템이 1차 선별한 10개의 금융 상품 중, 사용자의 프로필에 맞춰 우대 혜택을 가장 많이 받을 수 있고 미래 설계에 도움이 되는 '최종 Top 3' 상품을 선정하세요.
    반드시 JSON 형식으로만 출력해야 합니다.
    """
    
    user_prompt = f"""
    [사용자 요청]
    주어진 10개의 상품 중 내 상황에 가장 잘 맞는 Top 3 금융 상품과 종합 자산 전략을 추천하세요.

    [사용자 프로필]
    {profile_text}

    [Top 10 후보 상품]
    {candidates_text}

    [출력 스키마 (JSON)]
    {{
    "summary": "string",
    "recommended_products": [
        {{
        "candidate_index": 1,
        "bank": "string",
        "name": "string",
        "why": "string",
        "benefit": "string",
        "caution": "string"
        }}
    ],
    "asset_strategy": "string"
    }}

    [규칙]
    - recommended_products는 반드시 3개를 선정하세요.
    - summary는 3~5문장으로 작성하고, 사용자 조건과 추천 상품 Top3를 반영하세요.
    - 각 상품의 why/benefit/caution은 각각 3줄 내외로 작성하세요.
    - 각 상품의 why는 '왜 이 사용자에게 맞는지'를 사용자 프로필 기준으로 명시하세요.
    - benefit은 기대 혜택(우대 금리, 한도 등)을 구체적으로 작성하세요.
    - caution은 가입 제한이나 우대조건 미달 시 주의사항을 작성하세요.
    - asset_strategy는 사용자의 자산, 소득, 목표를 고려한 재무 조언을 300자 내외로 작성하세요.
    - JSON 외 다른 텍스트 출력은 절대 금지합니다.
    """

    # 4. LLM API 호출
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2,
    )
    
    # 5. LLM 응답 결과 JSON 파싱 및 매핑
    full_report_text = response.choices[0].message.content
    finance_top3 = []

    try:
        finance_report = json.loads(full_report_text)
    except json.JSONDecodeError:
        finance_report = {
            "summary": "분석 리포트를 생성하는 중 오류가 발생했습니다.", 
            "recommended_products": [], 
            "asset_strategy": ""
        }
    
    # 실제 상품 매핑
    recommended_list = finance_report.get("recommended_products", [])
    for item in recommended_list:
        idx = int(item.get("candidate_index", 1)) - 1
        if 0 <= idx < len(top10_candidates):
            finance_top3.append(top10_candidates[idx])
            
        item.pop("candidate_index", None)
        
    # 파싱 실패 처리
    if len(finance_top3) < 3:
        finance_top3 = top10_candidates[:3]
        
    return finance_top3, finance_report