from datetime import date


def generate_fake_housing_memo(user_profile: dict) -> dict:
    city = user_profile["region"]["city"]
    gu = user_profile["region"]["gu"]
    return {
        "summary": (
            f"{city} {gu} 기준으로 청년 대상 주거정책을 우선 검토했습니다. "
            "단기적으로는 신청 가능성이 높은 지원부터 진행하고, 중기적으로 전세 전환 옵션을 병행합니다."
        ),
        "eligible_policies": [
            {
                "name": "행복주택(예시)",
                "why": "청년(무주택) 대상이며 공공임대 유형으로 주거비 부담을 낮출 수 있음",
                "benefit": "임대료 절감 + 안정적 거주",
                "caution": "공고 시기/경쟁률 높음, 자격서류 준비 필요",
            },
            {
                "name": "청년 월세 지원(예시)",
                "why": "월세 부담 완화에 직접적 효과",
                "benefit": "월 지출 감소로 자산 형성 여력 증가",
                "caution": "소득/거주 요건, 중복수혜 제한 확인 필요",
            },
            {
                "name": "청년 전세자금대출(예시)",
                "why": "전세 전환 시 초기 목돈 부담을 낮춤",
                "benefit": "저금리 대출로 이자 부담 완화",
                "caution": "보증/심사 요건, 상환 계획 필수",
            },
        ],
        "strategy": (
            "전략: (1) 당장 1~3개월은 월세/공공임대 공고를 중심으로 ‘진입’ 확률을 높이고, "
            "(2) 동시에 전세 전환을 위한 대출 요건과 보증 가능 여부를 확인해 ‘사다리’ 옵션을 확보합니다. "
            "(3) 자격 서류(무주택/소득/재직 등)를 선제적으로 준비해 공고 즉시 신청 가능한 상태를 유지합니다."
        ),
        "evidence": [
            {"source": "policy_json_stub", "snippet": "청년 대상/무주택/소득 요건 등(예시 근거)"},
        ],
        "generated_at": str(date.today()),
    }


def generate_fake_finance_memo(user_profile: dict) -> dict:
    income = user_profile["monthly_income_m"]
    budget = user_profile["monthly_housing_budget_m"]
    banks = user_profile.get("banks", [])
    risk = user_profile.get("risk_pref", None)

    risk_txt = f"(리스크 성향: {risk})" if risk else "(리스크 성향: 미입력)"
    bank_txt = ", ".join(banks) if banks else "미입력"

    return {
        "summary": (
            f"월 소득 {income}만원 기준으로 저축 여력과 목표(주거비 {budget}만원)를 고려해 "
            f"단기 비상금 + 중기 목돈 마련 구조를 제안합니다. {risk_txt}\n"
            f"자주 쓰는 은행: {bank_txt}"
        ),
        "recommended_products": [
            {
                "name": "청년 우대 적금(예시)",
                "why": "청년 우대 금리/조건 충족 가능성이 높음",
                "benefit": "목돈 마련 속도 개선",
                "risk": "중도해지 시 금리 손실",
            },
            {
                "name": "비상금 통장/파킹통장(예시)",
                "why": "유동성 확보로 예상치 못한 지출 대응",
                "benefit": "현금흐름 안정화",
                "risk": "금리 변동 가능",
            },
            {
                "name": "전세자금대출 비교(예시)",
                "why": "전세 전환 시 레버리지 활용",
                "benefit": "초기 자금 부담 감소",
                "risk": "금리/상환 리스크",
            },
        ],
        "asset_strategy": (
            "전략: (1) 1~2개월치 생활비를 비상금으로 확보한 뒤, "
            "(2) 월 고정 저축액을 설정(적금/정기적립)하고, "
            "(3) 전세 전환 가능성이 있다면 대출 한도/보증 조건을 조기 점검해 실행 가능성을 확보합니다."
        ),
        "evidence": [
            {"source": "api_stub", "snippet": "금융상품 한눈에 API 응답 기반 필터링(예시)"},
        ],
        "generated_at": str(date.today()),
    }


def generate_fake_integrated_plan(user_profile: dict, housing_memo: dict, finance_memo: dict) -> dict:
    city = user_profile["region"]["city"]
    gu = user_profile["region"]["gu"]

    integrated_summary = (
        f"통합 전략: {city} {gu} 기준 주거비 부담을 낮추는 정책(공공임대/월세지원)을 우선 적용하고, "
        "절감된 현금흐름을 ‘비상금 → 적금/목돈’으로 전환합니다. "
        "중기적으로 전세 전환 가능성을 열어두되(대출/보증 조건 선점), 신청/서류 준비를 선행해 실행력을 확보합니다."
    )

    conflicts = [
        {
            "issue": "일부 주거 지원은 중복 수혜 제한 가능",
            "resolution": "주요 1~2개 정책을 우선순위로 두고, 나머지는 조건 충족 여부 확인 후 보조로 사용",
        }
    ]

    checklist = [
        "무주택 확인 서류(예: 주민등록등본/초본 등)",
        "소득 증빙(근로소득원천징수/급여명세 등)",
        "재직/사업 증빙(해당 시)",
        "임대차 계약 관련 서류(전세/월세 전환 시)",
    ]

    return {
        "integrated_summary": integrated_summary,
        "conflicts_and_resolutions": conflicts,
        "checklist": checklist,
        "generated_at": str(date.today()),
    }


def generate_fake_roadmap(user_profile: dict, housing_memo: dict, finance_memo: dict) -> list:
    return [
        {"time": "현재", "actions": ["사용자 조건 확정(소득/자산/부채)", "주거/금융 자격 요건 체크리스트 준비"]},
        {"time": "1개월", "actions": ["행복주택/월세지원 공고 모니터링", "비상금 통장 개설 및 1~2개월치 확보"]},
        {"time": "3개월", "actions": ["청년 우대 적금 가입(고정 저축 시작)", "전세자금대출/보증 조건 사전 점검"]},
        {"time": "6개월", "actions": ["주거 지원 신청(가능 공고 시)", "저축액 증액/지출 구조 점검(예산 리밸런싱)"]},
        {"time": "12개월", "actions": ["전세 전환 가능성 평가(대출 실행 포함)", "다음 단계(이직/소득상승/주거 상향) 계획 업데이트"]},
    ]
