import streamlit as st
import pandas as pd


def render_user_form():
    st.subheader("1) 🧑‍💼 사용자 정보 입력")

    BANK_OPTIONS = [
        "국민은행", "신한은행", "우리은행", "하나은행", "농협은행",
        "기업은행", "카카오뱅크", "토스뱅크", "케이뱅크",
        "부산은행", "대구은행", "광주은행", "전북은행", "경남은행",
        "수협은행", "SC제일은행", "씨티은행",
    ]

    with st.form("user_form"):
        col1, col2, col3 = st.columns(3)

        with col1:
            age = st.number_input("나이", min_value=18, max_value=45, value=25, step=1)
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
            default=["카카오뱅크"] if "카카오뱅크" in BANK_OPTIONS else [],
        )

        submitted = st.form_submit_button("분석 시작")

    if not submitted:
        return None

    if not banks:
        st.error("자주 쓰는 은행을 최소 1개 이상 선택해주세요.")
        return None

    return {
        "age": int(age),
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
    st.write(housing_memo["summary"])

    with st.expander("추천 정책 보기", expanded=True):
        for p in housing_memo["eligible_policies"]:
            st.markdown(f"**• {p['name']}**")
            st.markdown(f"- 이유: {p['why']}")
            st.markdown(f"- 기대효과: {p['benefit']}")
            st.markdown(f"- 주의: {p['caution']}")
            st.markdown("---")

    st.markdown("**전문가 의견(전략)**")
    st.write(housing_memo["strategy"])


def render_finance_section(finance_memo: dict):
    st.subheader("3) 금융 전략 의견서")
    st.write(finance_memo["summary"])

    with st.expander("추천 상품 보기", expanded=True):
        for p in finance_memo["recommended_products"]:
            st.markdown(f"**• {p['name']}**")
            st.markdown(f"- 이유: {p['why']}")
            st.markdown(f"- 기대효과: {p['benefit']}")
            st.markdown(f"- 리스크: {p['risk']}")
            st.markdown("---")

    st.markdown("**전문가 의견(자산 마련 전략)**")
    st.write(finance_memo["asset_strategy"])


def render_integrated_section(integrated_plan: dict):
    st.subheader("4) 통합 전략 요약(메인 에이전트)")
    st.write(integrated_plan["integrated_summary"])

    with st.expander("충돌/중복 및 해결 방안", expanded=True):
        for item in integrated_plan.get("conflicts_and_resolutions", []):
            st.markdown(f"**- 이슈:** {item['issue']}")
            st.markdown(f"**  해결:** {item['resolution']}")
            st.markdown("---")

    with st.expander("신청/준비 체크리스트", expanded=True):
        for c in integrated_plan.get("checklist", []):
            st.markdown(f"- {c}")


def render_roadmap(roadmap: list):
    """
    타임라인 카드 + 진행선(세로 타임라인) UI
    - 상단: 기간 선택(현재/3/6/12개월)
    - 본문: 세로 타임라인(점/선) + 카드(핵심 2~3개)
    - 카드 하단: expander로 전체 액션
    """
    st.subheader("5) 시각적 로드맵")

    # ---- 1) 기간 선택
    # roadmap 데이터에는 "1개월"도 있을 수 있으니 내부 정렬용으로 포함.
    order_map = {"현재": 0, "1개월": 1, "3개월": 2, "6개월": 3, "12개월": 4}

    allowed_select = ["현재", "3개월", "6개월", "12개월"]
    selected = st.selectbox("보고 싶은 로드맵 구간 선택", allowed_select, index=0)
    selected_order = order_map[selected]

    # ---- 2) 정렬/필터
    df = pd.DataFrame(roadmap).copy()
    df["order"] = df["time"].map(order_map).fillna(999).astype(int)
    df = df.sort_values("order")
    df_show = df[df["order"] <= selected_order].copy()

    # ---- 3) 스타일(CSS) 주입
    st.markdown(
        """
<style>
/* 전체 타임라인 컨테이너 */
.timeline-wrap{
  position: relative;
  padding-left: 10px;
  margin-top: 10px;
}

/* 한 줄(row) */
.tl-row{
  display: grid;
  grid-template-columns: 90px 24px 1fr;
  column-gap: 12px;
  align-items: start;
  margin-bottom: 14px;
}

/* 왼쪽 시간 라벨 */
.tl-time{
  font-weight: 700;
  font-size: 15px;
  line-height: 24px;
  color: #111827;
  padding-top: 2px;
}

/* 가운데 점/선 */
.tl-mid{
  position: relative;
  width: 24px;
  min-height: 40px;
}
.tl-dot{
  position: absolute;
  top: 6px;
  left: 7px;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #2563EB;
}
.tl-line{
  position: absolute;
  top: 18px;
  left: 11px;
  width: 2px;
  height: calc(100% + 14px);
  background: #D1D5DB;
}

/* 오른쪽 카드 */
.tl-card{
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  padding: 12px 14px;
  background: #FFFFFF;
}
.tl-card-title{
  font-weight: 700;
  margin-bottom: 6px;
}
.tl-bullets{
  margin: 0;
  padding-left: 18px;
}
.tl-bullets li{
  margin-bottom: 4px;
  line-height: 1.4;
}
.tl-muted{
  color: #6B7280;
  font-size: 12px;
  margin-top: 6px;
}
</style>
        """,
        unsafe_allow_html=True,
    )

    # ---- 4) 렌더링(카드 + 진행선)
    st.markdown('<div class="timeline-wrap">', unsafe_allow_html=True)

    records = df_show.to_dict(orient="records")
    for i, step in enumerate(records):
        t = step.get("time", "")
        actions = step.get("actions", []) or []

        # 카드에는 핵심 2~3개만
        key_actions = actions[:3]
        remaining = actions[3:]

        # 마지막 줄이면 아래 라인을 안 그림
        is_last = (i == len(records) - 1)

        bullets_html = "".join([f"<li>{a}</li>" for a in key_actions]) if key_actions else "<li>-</li>"
        line_html = "" if is_last else '<div class="tl-line"></div>'

        st.markdown(
            f"""
<div class="tl-row">
  <div class="tl-time">{t}</div>
  <div class="tl-mid">
    <div class="tl-dot"></div>
    {line_html}
  </div>
  <div class="tl-card">
    <div class="tl-card-title">핵심 액션</div>
    <ul class="tl-bullets">
      {bullets_html}
    </ul>
    <div class="tl-muted">선택 구간({selected}) 기준으로 표시됩니다.</div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )

        # “자세히 보기(펼치기)” - 전체 액션을 expander로
        # expander는 HTML 내부에 넣기 어렵기 때문에 row 아래에 Streamlit 컴포넌트로 붙인다.
        with st.expander(f"{t} - 자세히 보기", expanded=False):
            if not actions:
                st.write("-")
            else:
                for a in actions:
                    st.markdown(f"- {a}")

    st.markdown("</div>", unsafe_allow_html=True)

    # ---- 5)  표 보기 유지
    with st.expander("표로도 보기", expanded=False):
        rows = []
        for step in records:
            rows.append(
                {
                    "기간": step.get("time", ""),
                    "핵심 액션": "\n".join([f"• {a}" for a in (step.get("actions", []) or [])]),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)
