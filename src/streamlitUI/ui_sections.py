import streamlit as st
import pandas as pd
import re



def render_user_form():
    st.subheader("1) 🧑‍💼 사용자 정보 입력")

    # 금융 데이터 기준 은행 리스트로 교체
    BANK_OPTIONS = [
        "부산은행",
        "농협은행주식회사",
        "경남은행",
        "중소기업은행",
        "광주은행",
        "제주은행",
        "국민은행",
        "우리은행",
        "신한은행",
        "주식회사 하나은행",
        "주식회사 케이뱅크",
        "전북은행",
        "수협은행",
        "한국산업은행",
        "주식회사 카카오뱅크",
        "한국스탠다드차타드은행",
        "토스뱅크 주식회사",
        "아이엠뱅크",
    ]

    with st.form("user_form"):
        col1, col2, col3 = st.columns(3)

        with col1:
            age = st.number_input("나이", min_value=18, max_value=45, value=25, step=1)

            # 성별 추가
            gender = st.selectbox("성별", ["남성", "여성"], index=0)

            household_type = st.selectbox("가구 유형", ["청년(1인가구)", "신혼부부", "기타"], index=0)
            region_city = st.text_input("거주 희망 시/도", value="서울특별시")

        with col2:
            region_gu = st.text_input("거주 희망 시/군/구", value="관악구")
            monthly_income = st.number_input("월 소득(만원)", min_value=0, value=250, step=10)

            # 선택 입력
            use_risk = st.checkbox("리스크 성향 입력(선택)", value=False)
            risk_pref = None
            if use_risk:
                risk_pref = st.selectbox("리스크 성향", ["보수", "중립", "공격"], index=1)

        with col3:
            assets = st.number_input("보유 자산(만원)", min_value=0, value=500, step=50)

            # 선택 입력
            use_debt = st.checkbox("부채 입력(선택)", value=False)
            debt = None
            if use_debt:
                debt = st.number_input("부채(만원)", min_value=0, value=0, step=50)

            monthly_housing_budget = st.number_input("월 주거 예산(만원)", min_value=0, value=60, step=5)

        rent_type = st.selectbox("주거 형태 선호", ["월세", "전세", "상관없음"], index=0)
        move_timeline = st.selectbox("입주 희망 시점", ["즉시", "1~3개월", "3~6개월", "6~12개월"], index=1)

        # 필수 + 복수 선택
        banks = st.multiselect(
            "자주 쓰는 은행(필수, 복수 선택 가능)",
            options=BANK_OPTIONS,
            default=["주식회사 카카오뱅크"] if "주식회사 카카오뱅크" in BANK_OPTIONS else [],
        )

        submitted = st.form_submit_button("분석 시작")

    if not submitted:
        return None

    if not banks:
        st.error("자주 쓰는 은행을 최소 1개 이상 선택해주세요.")
        return None

    return {
        "age": int(age),

        
        "gender": gender,

        "household_type": household_type,
        "region": {"city": region_city.strip(), "gu": region_gu.strip()},
        "monthly_income_m": int(monthly_income),
        "assets_m": int(assets),
        "debt_m": None if debt is None else int(debt),
        "monthly_housing_budget_m": int(monthly_housing_budget),
        "rent_type": rent_type,
        "move_timeline": move_timeline,
        "risk_pref": risk_pref,
        "banks": banks,
    }


def render_user_profile_summary(user_profile: dict):
    st.subheader("입력 요약")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("나이", f'{user_profile["age"]}세')

        
        st.write("성별:", user_profile.get("gender", "-"))

        st.write("가구 유형:", user_profile["household_type"])
        st.write("주거 형태:", user_profile["rent_type"])

    with col2:
        city = user_profile["region"]["city"]
        gu = user_profile["region"]["gu"]
        st.write("희망 지역:", f"{city} {gu}")
        st.write("입주 시점:", user_profile["move_timeline"])
        st.write("자주 쓰는 은행:", ", ".join(user_profile.get("banks", [])))

    with col3:
        st.write("월 소득:", f'{user_profile["monthly_income_m"]}만원')
        st.write("보유 자산:", f'{user_profile["assets_m"]}만원')

        debt = user_profile.get("debt_m")
        st.write("부채:", f"{debt}만원" if debt is not None else "-(미입력)")

        risk = user_profile.get("risk_pref")
        st.write("리스크 성향:", risk if risk is not None else "-(미입력)")

        st.write("주거 예산:", f'{user_profile["monthly_housing_budget_m"]}만원')

def render_housing_section(housing_memo: dict):
    st.subheader("2) 주거 전략 의견서")

    status = housing_memo.get("_status", "ok")

    # summary 출력
    if status == "error":
        st.error("주거 정책 연동에 실패했습니다.")
        st.write(housing_memo.get("summary", ""))
    else:
        st.write(housing_memo.get("summary", ""))

    # 추천 정책
    with st.expander("추천 정책 보기", expanded=True):
        policies = housing_memo.get("eligible_policies", []) or []

        if not policies:
            if status == "error":
                st.info("현재 정책 추천을 불러올 수 없습니다.")
            else:
                st.info("조건에 맞는 정책이 없습니다.")
        else:
            for p in policies:
                st.markdown(f"**• {p.get('name','')}**")
                st.markdown(f"- 이유: {p.get('why','')}")
                st.markdown(f"- 기대효과: {p.get('benefit','')}")
                st.markdown(f"- 주의: {p.get('caution','')}")
                st.markdown("---")

    # 전략 (있는 경우만)
    strategy = housing_memo.get("strategy", "")
    if strategy:
        st.markdown("**전문가 의견(전략)**")
        st.write(strategy)

    


def render_finance_section(finance_memo: dict):
    st.subheader("3) 금융 전략 의견서")
    st.write(finance_memo["summary"])

    with st.expander("추천 상품 보기", expanded=True):
        for p in finance_memo["recommended_products"]:
            st.markdown(f"**• {p.get('name', '-') }**")

            bank = p.get("bank", "")
            if bank:
                st.markdown(f"- 은행: {bank}")

            st.markdown(f"- 이유: {p.get('why', '-')}")
            st.markdown(f"- 기대효과: {p.get('benefit', '-')}")

            #  risk 대신 caution 중심 + 폴백
            caution_text = p.get("caution") or p.get("risk") or "-(미기재)"
            st.markdown(f"- 주의: {caution_text}")

            st.markdown("---")

    st.markdown("**전문가 의견(자산 마련 전략)**")
    st.write(finance_memo["asset_strategy"])


def _split_markdown_roadmap(md: str):
    """
    Markdown에서 '## 4.'로 시작하는 로드맵 섹션을 찾아:
    - before: 로드맵 이전 텍스트
    - after: 로드맵 이후 텍스트
    못 찾으면 roadmap=None
    """
    if not md:
        return "", None, ""

    # '## 4.' 또는 '## 4 ' 형태 모두 대응
    pattern = r"(^##\s*4[\.\s].*?$)(.*?)(?=^##\s*\d+[\.\s]|\Z)"
    m = re.search(pattern, md, flags=re.MULTILINE | re.DOTALL)

    if not m:
        return md, None, ""

    start = m.start()
    end = m.end()

    before = md[:start].strip()
    roadmap = md[start:end].strip()
    after = md[end:].strip()

    return before, roadmap, after

#4. 통합전략 에이전트
def render_integrated_section(integrated_plan: dict, final_report_markdown: str = None):
    st.subheader("4) 통합 전략 요약(메인 에이전트)")

    # 1) Markdown 리포트가 있으면, 그걸 '정본'으로 출력
    if final_report_markdown:
        before, roadmap_section, after = _split_markdown_roadmap(final_report_markdown)

        # 로드맵 구간만 접고, 나머지는 그대로 출력
        if before:
            st.markdown(before)
        if roadmap_section:
            with st.expander("📌 (접기/펼치기) 리포트 원문 로드맵 섹션", expanded=False):
                st.markdown(roadmap_section)
        if after:
            st.markdown(after)

    # 2) Markdown이 없으면 fallback으로 integrated_summary 출력
    else:
        st.write(integrated_plan.get("integrated_summary", ""))

    # 3) JSON 구조(충돌/체크리스트)는 보조정보로 유지
    with st.expander("충돌/중복 및 해결 방안", expanded=False):
        items = integrated_plan.get("conflicts_and_resolutions", [])
        if not items:
            st.info("표시할 항목이 없습니다.")
        for item in items:
            st.markdown(f"**- 이슈:** {item.get('issue','')}")
            st.markdown(f"**  해결:** {item.get('resolution','')}")
            why = item.get("why_it_matters", "")
            if why:
                st.caption(why)
            st.markdown("---")

    with st.expander("신청/준비 체크리스트", expanded=False):
        checklist = integrated_plan.get("checklist", [])
        if not checklist:
            st.info("표시할 항목이 없습니다.")
        for c in checklist:
            # checklist가 dict로 오는 경우도 있으니 안전 처리
            if isinstance(c, dict):
                st.markdown(f"- {c.get('item','')} ({c.get('deadline','')})  \n  {c.get('notes','')}")
            else:
                st.markdown(f"- {c}")

