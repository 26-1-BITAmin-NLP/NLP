from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import re
# --- Text helpers ---
def _sanitize_text(s: str) -> str:
    """
    ReportLab + 일반 TTF(예: Pretendard)에서 깨지기 쉬운 문자(일부 기호)를 안전 문자로 치환.

    """
    replacements = {
        "·": "-",  # middle dot
    }
    for k, v in replacements.items():
        s = s.replace(k, v)

    
    s = "".join(ch for ch in s if ord(ch) <= 0xFFFF)
    return s


def _safe(v: Any) -> str:
    if v is None:
        return "-"
    return _sanitize_text(str(v))


# --- Font register ---
def _register_korean_font() -> Dict[str, str]:
    """
    프로젝트 내부 assets/fonts 폴더의 Pretendard TTF를 등록하고 폰트 이름을 반환한다.
    """
    # pdf_report.py 위치 기준으로 
    base_dir = Path(__file__).resolve().parents[2]
    font_dir = base_dir / "assets" / "fonts"

    fonts = {
        "Pretendard": font_dir / "Pretendard-Regular.ttf",
        "Pretendard-Medium": font_dir / "Pretendard-Medium.ttf",
        "Pretendard-SemiBold": font_dir / "Pretendard-SemiBold.ttf",
    }

    for name, path in fonts.items():
        if not path.exists():
            raise RuntimeError(f"폰트 파일이 없습니다: {path}")
        try:
            pdfmetrics.registerFont(TTFont(name, str(path)))
        except Exception as e:
            raise RuntimeError(f"폰트 등록 실패: {name} ({path}) / {e}")

    return {
        "regular": "Pretendard",
        "medium": "Pretendard-Medium",
        "semibold": "Pretendard-SemiBold",
    }

def strip_md_for_pdf(md: str) -> str:
    if not md:
        return ""

    text = md

    # 1) 코드블록 제거(있다면)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    # 2) 헤더 기호 제거: #, ##, ### ...
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)

    # 3) 굵게/기울임 기호 제거: **
    text = text.replace("**", "")
    # 문장 중간의 단독 '*'가 bullet로 쓰인 경우가 많으니 bullet 패턴만 처리
    text = re.sub(r"^\s*[\*\-]\s+", "• ", text, flags=re.MULTILINE)

    # 4) 과도한 공백 정리
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return text

def generate_pdf(
    user_profile: Dict[str, Any],
    housing_memo: Dict[str, Any] | None,
    finance_memo: Dict[str, Any] | None,
    integrated_plan: Dict[str, Any] | None,
    final_report_markdown: str | None = None,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=36,
        bottomMargin=36,
        leftMargin=36,
        rightMargin=36,
    )

    font_map = _register_korean_font()

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleKR",
        parent=styles["Title"],
        fontName=font_map["semibold"],
        fontSize=18,
        leading=22,
        spaceAfter=10,
    )

    h_style = ParagraphStyle(
        "HeadingKR",
        parent=styles["Heading2"],
        fontName=font_map["medium"],
        fontSize=12,
        leading=16,
        spaceBefore=8,
        spaceAfter=6,
    )

    body = ParagraphStyle(
        "BodyKR",
        parent=styles["BodyText"],
        fontName=font_map["regular"],
        fontSize=10,
        leading=14,
    )

    story = []

    # 0) Title
    story.append(Paragraph(_safe("청년 미래 설계 보고서"), title_style))
    story.append(Paragraph(_safe("주거 + 금융 의견서를 통합해 로드맵과 실행 계획을 제공합니다."), body))
    story.append(Spacer(1, 12))

    # 1) User Profile
    story.append(Paragraph(_safe("1. 사용자 프로필 및 요구사항"), h_style))

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
    story.append(Paragraph(_safe("<br/>".join(profile_lines)), body))
    story.append(Spacer(1, 10))

    # 2) Housing
    story.append(Paragraph(_safe("2. 주거 전략 의견"), h_style))
    if housing_memo is None:
        story.append(Paragraph(_safe("- 주거 의견서가 아직 생성되지 않았습니다."), body))
    else:
        story.append(Paragraph(_safe(f"<b>요약</b><br/>{_safe(housing_memo.get('summary'))}"), body))
        story.append(Spacer(1, 6))

        policies = housing_memo.get("eligible_policies", [])
        if policies:
            story.append(Paragraph(_safe("<b>추천 정책</b>"), body))
            for p in policies:
                line = (
                    f"• <b>{_safe(p.get('name'))}</b><br/>"
                    f" 이유: {_safe(p.get('why'))}<br/>"
                    f" 기대효과: {_safe(p.get('benefit'))}<br/>"
                    f" 주의: {_safe(p.get('caution'))}"
                )
                story.append(Paragraph(_safe(line), body))
                story.append(Spacer(1, 6))

        story.append(Paragraph(_safe(f"<b>전략</b><br/>{_safe(housing_memo.get('strategy'))}"), body))

    story.append(Spacer(1, 12))

    # 3) Finance
    story.append(Paragraph(_safe("3. 금융 전략 의견"), h_style))
    if finance_memo is None:
        story.append(Paragraph(_safe("- 금융 의견서가 아직 생성되지 않았습니다."), body))
    else:
        story.append(Paragraph(_safe(f"<b>요약</b><br/>{_safe(finance_memo.get('summary'))}"), body))
        story.append(Spacer(1, 6))

        products = finance_memo.get("recommended_products", [])
        if products:
            story.append(Paragraph(_safe("<b>추천 상품</b>"), body))
            for p in products:
                line = (
                    f"•<b>{_safe(p.get('name'))}</b><br/>"
                    f" 이유: {_safe(p.get('why'))}<br/>"
                    f" 기대효과: {_safe(p.get('benefit'))}<br/>"
                    f" 리스크: {_safe(p.get('risk'))}"
                )
                story.append(Paragraph(_safe(line), body))
                story.append(Spacer(1, 6))

        story.append(Paragraph(_safe(f"<b>자산 마련 전략</b><br/>{_safe(finance_memo.get('asset_strategy'))}"), body))

    story.append(Spacer(1, 12))

    # 4) Integrated
    story.append(Paragraph(_safe("4. 통합 전략 요약"), h_style))
    if integrated_plan is None:
        story.append(Paragraph(_safe("- 통합 전략이 아직 생성되지 않았습니다."), body))
    else:
        md = final_report_markdown or integrated_plan.get("integrated_summary") or ""
           
        if "## 4" in md:
            md = md.split("## 4")[0].strip()

        md = strip_md_for_pdf(md)              # 마크다운 문법 제거
        md = _safe(md).replace("\n", "<br/>")  # 줄바꿈만 유지
        story.append(Paragraph(md, body))
        story.append(Spacer(1, 6))

        conflicts = integrated_plan.get("conflicts_and_resolutions", [])
        if conflicts:
            story.append(Paragraph(_safe("<b>충돌/중복 및 해결</b>"), body))
            for item in conflicts:
                line = f"- 이슈: {_safe(item.get('issue'))}<br/>  해결: {_safe(item.get('resolution'))}"
                story.append(Paragraph(_safe(line), body))
                story.append(Spacer(1, 4))

        checklist = integrated_plan.get("checklist", [])
        if checklist:
                    checklist = integrated_plan.get("checklist", [])
        if checklist:
            story.append(Spacer(1, 6))
            story.append(Paragraph(_safe("<b>체크리스트</b>"), body))
            story.append(Spacer(1, 4))

            for c in checklist:
                # dict 형태(UI와 동일한 출력)
                if isinstance(c, dict):
                    item = _safe(c.get("item", ""))
                    deadline = _safe(c.get("deadline", ""))
                    notes = _safe(c.get("notes", ""))

                    line1 = f"- {item}" + (f" ({deadline})" if deadline and deadline != "-" else "")
                    story.append(Paragraph(_safe(line1), body))

                    if notes and notes != "-":
                        story.append(Paragraph(_safe(f"&nbsp;&nbsp;{notes}"), body))

                    story.append(Spacer(1, 4))

                # 문자열 리스트 형태도 지원
                else:
                    story.append(Paragraph(_safe(f"- {_safe(c)}"), body))
                    story.append(Spacer(1, 4))

        # 5) 12개월 로드맵 (Markdown에서 추출)
    if final_report_markdown and "12개월" in final_report_markdown:

        story.append(Spacer(1, 10))
        story.append(Paragraph(_safe("5. 12개월 밀착 실행 로드맵"), h_style))
        story.append(Spacer(1, 6))

        md = final_report_markdown

        #  로드맵 표 부분 추출
        try:
            section = md.split("12개월")[1]
        except:
            section = ""

        lines = section.split("\n")

        #  | 로 시작하는 테이블 라인만 추출
        table_rows = []
        for line in lines:
            if line.strip().startswith("|"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                table_rows.append(cells)

        #  구분선 제거 (|---|---|)
        table_rows = [
            row for row in table_rows
            if not all(set(cell) <= {"-"} for cell in row)
        ]

        # PDF Table 생성
        if table_rows:
            table = Table(table_rows, repeatRows=1)

            table.setStyle(TableStyle([
                ("FONTNAME", (0,0), (-1,-1), font_map["regular"]),
                ("FONTSIZE", (0,0), (-1,-1), 9),
                ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
                ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ]))

            story.append(table)
            story.append(Spacer(1, 8))                
    story.append(Spacer(1, 12))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes