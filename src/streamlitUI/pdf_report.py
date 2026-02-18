from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont


def _safe(v: Any) -> str:
    if v is None:
        return "-(미입력)"
    return str(v)


def _register_korean_font() -> str:
    """
    외부 TTF 없이도 한글이 안 깨지도록 CID 폰트를 등록한다.
    환경에 따라 아래 폰트 중 하나는 동작한다.
    """
    candidates = ["HYGothic-Medium", "HYSMyeongJo-Medium"]
    for name in candidates:
        try:
            pdfmetrics.registerFont(UnicodeCIDFont(name))
            return name
        except Exception:
            continue

    # 최후: 기본 폰트(한글 깨질 수 있음)
    return "Helvetica"


def generate_pdf(
    user_profile: Dict[str, Any],
    housing_memo: Dict[str, Any] | None,
    finance_memo: Dict[str, Any] | None,
    integrated_plan: Dict[str, Any] | None,
    roadmap: List[Dict[str, Any]] | None,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=36, bottomMargin=36, leftMargin=36, rightMargin=36)

    font_name = _register_korean_font()

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleKR",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=18,
        leading=22,
        spaceAfter=10,
    )

    h_style = ParagraphStyle(
        "HeadingKR",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=12,
        leading=16,
        spaceBefore=8,
        spaceAfter=6,
    )

    body = ParagraphStyle(
        "BodyKR",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=10,
        leading=14,
    )

    story = []

    # 0) Title
    story.append(Paragraph("청년 미래 설계 보고서", title_style))
    story.append(Paragraph("주거(정책 RAG) + 금융(API) 의견서를 통합해 로드맵과 실행 계획을 제공합니다.", body))
    story.append(Spacer(1, 12))

    # 1) User Profile
    story.append(Paragraph("1. 사용자 프로필 및 요구사항", h_style))

    city = user_profile.get("region", {}).get("city", "")
    gu = user_profile.get("region", {}).get("gu", "")
    banks = user_profile.get("banks", [])

    profile_lines = [
        f"- 나이: {_safe(user_profile.get('age'))}세",
        f"- 가구 유형: {_safe(user_profile.get('household_type'))}",
        f"- 희망 지역: {_safe(city)} {_safe(gu)}",
        f"- 월 소득(만원): {_safe(user_profile.get('monthly_income_m'))}",
        f"- 보유 자산(만원): {_safe(user_profile.get('assets_m'))}",
        f"- 부채(만원): {_safe(user_profile.get('debt_m'))}",
        f"- 월 주거 예산(만원): {_safe(user_profile.get('monthly_housing_budget_m'))}",
        f"- 주거 형태 선호: {_safe(user_profile.get('rent_type'))}",
        f"- 입주 희망 시점: {_safe(user_profile.get('move_timeline'))}",
        f"- 리스크 성향: {_safe(user_profile.get('risk_pref'))}",
        f"- 자주 쓰는 은행: {', '.join(banks) if banks else '-'}",
    ]
    story.append(Paragraph("<br/>".join(profile_lines), body))
    story.append(Spacer(1, 10))

    # 2) Housing
    story.append(Paragraph("2. 주거 전략 의견(주거 에이전트 의견)", h_style))
    if housing_memo is None:
        story.append(Paragraph("- 주거 의견서가 아직 생성되지 않았습니다.", body))
    else:
        story.append(Paragraph(f"<b>요약</b><br/>{_safe(housing_memo.get('summary'))}", body))
        story.append(Spacer(1, 6))

        policies = housing_memo.get("eligible_policies", [])
        if policies:
            story.append(Paragraph("<b>추천 정책</b>", body))
            for p in policies:
                line = (
                    f"• <b>{_safe(p.get('name'))}</b><br/>"
                    f"- 이유: {_safe(p.get('why'))}<br/>"
                    f"- 기대효과: {_safe(p.get('benefit'))}<br/>"
                    f"- 주의: {_safe(p.get('caution'))}"
                )
                story.append(Paragraph(line, body))
                story.append(Spacer(1, 6))

        story.append(Paragraph(f"<b>전략</b><br/>{_safe(housing_memo.get('strategy'))}", body))

    story.append(Spacer(1, 12))

    # 3) Finance
    story.append(Paragraph("3. 금융 전략 의견(금융 에이전트 의견)", h_style))
    if finance_memo is None:
        story.append(Paragraph("- 금융 의견서가 아직 생성되지 않았습니다.", body))
    else:
        story.append(Paragraph(f"<b>요약</b><br/>{_safe(finance_memo.get('summary'))}", body))
        story.append(Spacer(1, 6))

        products = finance_memo.get("recommended_products", [])
        if products:
            story.append(Paragraph("<b>추천 상품</b>", body))
            for p in products:
                line = (
                    f"• <b>{_safe(p.get('name'))}</b><br/>"
                    f"- 이유: {_safe(p.get('why'))}<br/>"
                    f"- 기대효과: {_safe(p.get('benefit'))}<br/>"
                    f"- 리스크: {_safe(p.get('risk'))}"
                )
                story.append(Paragraph(line, body))
                story.append(Spacer(1, 6))

        story.append(Paragraph(f"<b>자산 마련 전략</b><br/>{_safe(finance_memo.get('asset_strategy'))}", body))

    story.append(Spacer(1, 12))

    # 4) Integrated
    story.append(Paragraph("4. 통합 전략 요약(메인 에이전트 의견)", h_style))
    if integrated_plan is None:
        story.append(Paragraph("- 통합 전략이 아직 생성되지 않았습니다.", body))
    else:
        story.append(Paragraph(_safe(integrated_plan.get("integrated_summary")), body))
        story.append(Spacer(1, 6))

        conflicts = integrated_plan.get("conflicts_and_resolutions", [])
        if conflicts:
            story.append(Paragraph("<b>충돌/중복 및 해결</b>", body))
            for item in conflicts:
                line = f"- 이슈: {_safe(item.get('issue'))}<br/>  해결: {_safe(item.get('resolution'))}"
                story.append(Paragraph(line, body))
                story.append(Spacer(1, 4))

        checklist = integrated_plan.get("checklist", [])
        if checklist:
            story.append(Spacer(1, 6))
            story.append(Paragraph("<b>체크리스트</b>", body))
            story.append(Paragraph("<br/>".join([f"- {_safe(x)}" for x in checklist]), body))

    story.append(Spacer(1, 12))

    # 5) Roadmap table
    story.append(Paragraph("5. 시각적 로드맵", h_style))
    if not roadmap:
        story.append(Paragraph("- 로드맵이 아직 생성되지 않았습니다.", body))
    else:
        table_data = [["기간", "핵심 액션"]]
        for step in roadmap:
            actions = step.get("actions", [])
            table_data.append([_safe(step.get("time")), "\n".join([f"• {a}" for a in actions])])

        tbl = Table(table_data, colWidths=[80, 420])
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("FONTNAME", (0, 0), (-1, -1), font_name),  # ✅ 한글 폰트 적용
                    ("ALIGN", (0, 0), (-1, 0), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                ]
            )
        )
        story.append(tbl)

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
