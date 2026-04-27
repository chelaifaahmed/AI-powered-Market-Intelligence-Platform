"""
analytics/pdf_exporter.py
--------------------------
Generates a professional PDF "Market Intelligence Brief" from OpportunitySignal
and MarketTrendArticle data.

Public API:
    generate_opportunity_brief(session) -> bytes
"""

from __future__ import annotations

import io
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.graphics.shapes import Drawing, Rect
from sqlalchemy.orm import Session

from database.models import (
    ArticleNlpResult,
    MarketTrendArticle,
    OpportunitySignal,
)

logger = logging.getLogger("analytics.pdf_exporter")

# ---------------------------------------------------------------------------
# Colour palette (matches dashboard)
# ---------------------------------------------------------------------------
DARK_HEADER = colors.HexColor("#0f172a")
INDIGO = colors.HexColor("#6366f1")
INDIGO_LIGHT = colors.HexColor("#e0e7ff")
WHITE = colors.white
SLATE_700 = colors.HexColor("#334155")
SLATE_400 = colors.HexColor("#94a3b8")
SLATE_100 = colors.HexColor("#f1f5f9")
RED_500 = colors.HexColor("#ef4444")
AMBER_500 = colors.HexColor("#f59e0b")
GREEN_500 = colors.HexColor("#22c55e")

PAGE_W, PAGE_H = A4
LEFT_MARGIN = 20 * mm
RIGHT_MARGIN = 20 * mm
TOP_MARGIN = 20 * mm
BOT_MARGIN = 25 * mm


# ---------------------------------------------------------------------------
# Narrative generator (mirrors dashboard generateBriefing)
# ---------------------------------------------------------------------------

def generate_brief_narrative(
    signals: List[Any],
    strong: int,
    moderate: int,
    weak: int,
    region_counts: Dict[str, int],
) -> str:
    """Generate an executive summary paragraph mirroring the dashboard briefing."""
    total = len(signals)
    if total == 0:
        return "No opportunity signals have been computed yet. Run the opportunity scorer to populate this brief."

    avg_score = round(sum(float(s.overall_score) for s in signals) / total)
    top = max(signals, key=lambda s: float(s.overall_score))
    regions = len(region_counts)

    if strong > 0:
        complaint = (top.top_complaint_types[0] if top.top_complaint_types else "multiple complaint categories")
        sector_label = "insurance companies" if top.entity_type == "insurance" else "automotive brands"
        percentile_line = ""
        if hasattr(top, "sector_percentile") and top.sector_percentile is not None:
            percentile_line = (
                f" {top.entity_name} ranks in the top {100 - top.sector_percentile}% most distressed "
                f"{sector_label} in our dataset."
            )
        narrative = (
            f"{strong} {'company is' if strong == 1 else 'companies are'} showing strong distress signals this month. "
            f"{top.entity_name} leads with a score of {round(float(top.overall_score))}/100, "
            f"driven by {complaint}. "
            f"This represents an immediate outreach opportunity for TEAMWILL's sales team."
            f"{percentile_line}"
        )
    elif any(float(s.complaint_score) > 60 for s in signals):
        complaint = (top.top_complaint_types[0] if top.top_complaint_types else "operational issues")
        narrative = (
            f"{top.entity_name} is the highest-priority opportunity (score: {round(float(top.overall_score))}/100). "
            f"Customer complaints center on {complaint}, which aligns with TEAMWILL's core ERP capabilities. "
            f"{moderate} companies show moderate signals worth monitoring."
        )
    else:
        narrative = (
            f"{total} companies tracked across {regions} {'region' if regions == 1 else 'regions'}. "
            f"Average opportunity score: {avg_score}/100. "
            f"Continue data collection to surface differentiated rankings."
        )

    narrative += f" {total} companies tracked across {regions} {'region' if regions == 1 else 'regions'}."
    return narrative


# ---------------------------------------------------------------------------
# Score bar drawing helper
# ---------------------------------------------------------------------------

def _score_bar(score: float, width: float = 80, height: float = 8) -> Drawing:
    """Return a ReportLab Drawing with a filled score bar."""
    d = Drawing(width, height)
    # Background
    d.add(Rect(0, 0, width, height, fillColor=SLATE_100, strokeColor=None))
    # Filled portion
    fill_w = max(1, (score / 100) * width)
    if score >= 70:
        bar_color = RED_500
    elif score >= 40:
        bar_color = AMBER_500
    else:
        bar_color = SLATE_400
    d.add(Rect(0, 0, fill_w, height, fillColor=bar_color, strokeColor=None))
    return d


def _unicode_bar(score: float, total_blocks: int = 10) -> str:
    """Return a Unicode block bar like ████░░░░░░."""
    filled = round((score / 100) * total_blocks)
    return "\u2588" * filled + "\u2591" * (total_blocks - filled)


# ---------------------------------------------------------------------------
# Recommended actions generator
# ---------------------------------------------------------------------------

def _generate_actions(signals: List[Any], region_counts: Dict[str, int]) -> List[str]:
    """Dynamically generate recommended action bullets."""
    actions = []
    top = max(signals, key=lambda s: float(s.overall_score)) if signals else None

    if top and float(top.overall_score) >= 60:
        complaint = (top.top_complaint_types[0] if top.top_complaint_types else "operational issues")
        actions.append(
            f"Contact {top.entity_name} ({top.entity_type}) network \u2014 "
            f"{complaint} spike suggests ERP gap."
        )

    tn_signals = [s for s in signals if s.region == "TN"]
    tn_no_data = [s for s in tn_signals if float(s.review_volume_score) > 70]
    if tn_no_data:
        actions.append(
            f"Prioritize digital presence audit for {len(tn_no_data)} TN insurance "
            f"{'company' if len(tn_no_data) == 1 else 'companies'} with no review data."
        )

    eu_signals = [s for s in signals if s.region == "EU"]
    if eu_signals:
        actions.append("Schedule quarterly review of EU opportunity scores.")

    if not actions:
        actions.append("Continue deepening review scraping across all tracked entities.")

    return actions


# ---------------------------------------------------------------------------
# Page template callbacks
# ---------------------------------------------------------------------------

def _header_footer(canvas, doc):
    """Draw header bar and footer on every page."""
    canvas.saveState()

    # --- Dark header bar ---
    canvas.setFillColor(DARK_HEADER)
    canvas.rect(0, PAGE_H - 45 * mm, PAGE_W, 45 * mm, fill=1, stroke=0)

    # TEAMWILL text
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 18)
    canvas.drawString(LEFT_MARGIN, PAGE_H - 18 * mm, "TEAMWILL")

    # Title line
    canvas.setFont("Helvetica", 13)
    canvas.drawString(LEFT_MARGIN, PAGE_H - 27 * mm, "Market Intelligence Brief")

    # Subtitle
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(SLATE_400)
    canvas.drawString(LEFT_MARGIN, PAGE_H - 34 * mm, "Automotive & Insurance Opportunity Report")

    # Date + generator
    now_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(SLATE_400)
    canvas.drawRightString(PAGE_W - RIGHT_MARGIN, PAGE_H - 18 * mm, now_str)
    canvas.drawRightString(
        PAGE_W - RIGHT_MARGIN, PAGE_H - 25 * mm,
        "Generated by: AI-Powered Market Intelligence Platform"
    )

    # --- Footer ---
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(SLATE_400)
    canvas.drawString(LEFT_MARGIN, 12 * mm, "Confidential \u2014 TEAMWILL Internal Use Only")
    canvas.drawRightString(PAGE_W - RIGHT_MARGIN, 12 * mm, f"Page {doc.page}")

    canvas.restoreState()


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_opportunity_brief(session: Session) -> bytes:
    """
    Query OpportunitySignal + MarketTrendArticle data and produce a
    professional 1-2 page PDF brief as bytes.
    """
    # ---- Fetch data ----
    signals = (
        session.query(OpportunitySignal)
        .order_by(OpportunitySignal.overall_score.desc())
        .limit(10)
        .all()
    )
    articles = (
        session.query(MarketTrendArticle)
        .filter(MarketTrendArticle.publication_date.isnot(None))
        .order_by(MarketTrendArticle.publication_date.desc())
        .limit(5)
        .all()
    )
    all_signals = session.query(OpportunitySignal).all()
    strong = sum(1 for s in all_signals if s.signal_strength == "strong")
    moderate = sum(1 for s in all_signals if s.signal_strength == "moderate")
    weak = sum(1 for s in all_signals if s.signal_strength == "weak")

    region_counts: Dict[str, int] = {}
    for s in all_signals:
        r = s.region or "unset"
        region_counts[r] = region_counts.get(r, 0) + 1

    # ---- Styles ----
    styles = getSampleStyleSheet()
    section_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=INDIGO,
        spaceAfter=6,
        spaceBefore=14,
        fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle(
        "BriefBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=14,
        textColor=SLATE_700,
    )
    small_style = ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=SLATE_400,
    )

    # ---- Build flowable story ----
    story: list = []

    # Section 1 — Executive Summary
    story.append(Paragraph("Executive Summary", section_style))
    narrative = generate_brief_narrative(signals, strong, moderate, weak, region_counts)
    story.append(Paragraph(narrative, body_style))
    story.append(Spacer(1, 8))

    # Section 2 — Top 5 Opportunities
    story.append(Paragraph("Top 5 Opportunities", section_style))
    top5 = signals[:5]
    if top5:
        header = ["Rank", "Company", "Type", "Region", "Score", "Bar", "Signal", "Top Complaint"]
        table_data = [header]
        for i, s in enumerate(top5, 1):
            complaint = s.top_complaint_types[0] if s.top_complaint_types else "\u2014"
            bar = _unicode_bar(float(s.overall_score))
            table_data.append([
                str(i),
                s.entity_name,
                s.entity_type.title(),
                s.region or "\u2014",
                f"{float(s.overall_score):.1f}",
                bar,
                s.signal_strength.title(),
                complaint,
            ])

        col_widths = [22, 75, 50, 40, 35, 65, 50, 90]
        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            # Header row
            ("BACKGROUND", (0, 0), (-1, 0), INDIGO),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("TEXTCOLOR", (0, 1), (-1, -1), SLATE_700),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (4, 0), (4, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.3, SLATE_400),
            # Alternating rows
            *[
                ("BACKGROUND", (0, r), (-1, r), SLATE_100)
                for r in range(2, len(table_data), 2)
            ],
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No opportunity signals computed yet.", body_style))
    story.append(Spacer(1, 8))

    # Section 3 — Score Breakdown (top 3)
    story.append(Paragraph("Score Breakdown \u2014 Top 3", section_style))
    top3 = signals[:3]
    if top3:
        bd_header = ["Company", "Complaint", "Sentiment", "Visibility", "Interpretation"]
        bd_data = [bd_header]
        for s in top3:
            cs = float(s.complaint_score)
            ss = float(s.sentiment_drop_score)
            vs = float(s.review_volume_score)
            if cs >= 60:
                interp = "High complaint rate \u2014 strong ERP need signal"
            elif vs >= 70:
                interp = "Low review visibility \u2014 digital presence gap"
            elif ss >= 50:
                interp = "Declining sentiment \u2014 operational stress"
            else:
                interp = "Moderate across all dimensions"
            bd_data.append([
                s.entity_name,
                f"{cs:.0f}",
                f"{ss:.0f}",
                f"{vs:.0f}",
                interp,
            ])
        bd_widths = [80, 55, 55, 55, 185]
        bt = Table(bd_data, colWidths=bd_widths, repeatRows=1)
        bt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), INDIGO),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("TEXTCOLOR", (0, 1), (-1, -1), SLATE_700),
            ("ALIGN", (1, 0), (3, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.3, SLATE_400),
            *[
                ("BACKGROUND", (0, r), (-1, r), SLATE_100)
                for r in range(2, len(bd_data), 2)
            ],
        ]))
        story.append(bt)
    story.append(Spacer(1, 8))

    # Section 4 — Regional Coverage
    story.append(Paragraph("Regional Coverage", section_style))
    region_parts = []
    for rname, cnt in sorted(region_counts.items(), key=lambda x: -x[1]):
        region_parts.append(f"{rname}: {cnt} {'company' if cnt == 1 else 'companies'}")
    story.append(Paragraph(" | ".join(region_parts), body_style))

    if region_counts:
        best_region = None
        best_avg = 0
        for rname in region_counts:
            rsigs = [s for s in all_signals if (s.region or "unset") == rname]
            if rsigs:
                ravg = sum(float(s.overall_score) for s in rsigs) / len(rsigs)
                if ravg > best_avg:
                    best_avg = ravg
                    best_region = rname
        if best_region:
            story.append(Paragraph(
                f"Highest average score: {best_region} ({best_avg:.1f}/100)",
                small_style,
            ))
    story.append(Spacer(1, 10))

    # ---- Page 2 content: Articles + Actions ----

    # Section 5 — Recent Market Articles
    story.append(Paragraph("Recent Market Articles", section_style))
    if articles:
        art_header = ["Title", "Source", "Date", "Sentiment"]
        art_data = [art_header]
        for a in articles:
            # Get sentiment from NLP results if available
            sentiment_tag = "\u2014"
            if a.nlp_results:
                label = a.nlp_results[0].sentiment_label
                if label:
                    sentiment_tag = label.value if hasattr(label, "value") else str(label)

            pub_date = a.publication_date.strftime("%Y-%m-%d") if a.publication_date else "\u2014"
            # Truncate title to fit
            title = a.title[:55] + "\u2026" if len(a.title) > 55 else a.title
            source = a.author or "\u2014"
            art_data.append([title, source, pub_date, sentiment_tag])

        art_widths = [200, 80, 65, 60]
        at = Table(art_data, colWidths=art_widths, repeatRows=1)
        at.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), INDIGO),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("TEXTCOLOR", (0, 1), (-1, -1), SLATE_700),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.3, SLATE_400),
            *[
                ("BACKGROUND", (0, r), (-1, r), SLATE_100)
                for r in range(2, len(art_data), 2)
            ],
        ]))
        story.append(at)
    else:
        story.append(Paragraph("No articles with publication dates available.", body_style))
    story.append(Spacer(1, 10))

    # Section 6 — Recommended Actions
    story.append(Paragraph("Recommended Actions", section_style))
    actions = _generate_actions(signals, region_counts)
    for action in actions:
        story.append(Paragraph(f"\u2022  {action}", body_style))
        story.append(Spacer(1, 3))

    # ---- Build PDF ----
    buf = io.BytesIO()
    content_frame = Frame(
        LEFT_MARGIN,
        BOT_MARGIN,
        PAGE_W - LEFT_MARGIN - RIGHT_MARGIN,
        PAGE_H - TOP_MARGIN - BOT_MARGIN - 30 * mm,  # room for header
        id="main",
    )
    page_tmpl = PageTemplate(id="brief", frames=[content_frame], onPage=_header_footer)

    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        pageTemplates=[page_tmpl],
        title="TEAMWILL Market Intelligence Brief",
        author="TEAMWILL AI Platform",
    )
    doc.build(story)
    buf.seek(0)
    pdf_bytes = buf.read()
    logger.info("PDF brief generated: %d bytes, %d pages", len(pdf_bytes), doc.page)
    return pdf_bytes


# ---------------------------------------------------------------------------
# Company Radar — single-company PDF brief
# ---------------------------------------------------------------------------

def generate_company_brief(profile: Dict[str, Any]) -> bytes:
    """
    Generate a pre-call intelligence PDF for a single company (car or insurance).
    profile: dict matching the CompanyProfile Pydantic schema from main.py.
    """
    styles = getSampleStyleSheet()

    section_style = ParagraphStyle(
        "CR_Section",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=INDIGO,
        spaceAfter=6,
        spaceBefore=14,
        fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle(
        "CR_Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=14,
        textColor=SLATE_700,
    )
    small_style = ParagraphStyle(
        "CR_Small",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=SLATE_400,
    )
    label_style = ParagraphStyle(
        "CR_Label",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=SLATE_400,
        fontName="Helvetica-Bold",
    )

    name = profile.get("name", "Unknown")
    company_type = profile.get("type", "")
    sector = profile.get("sector", "")
    region = profile.get("region") or "—"
    country = profile.get("country") or "—"
    score = profile.get("score")
    score_percentile = profile.get("score_percentile")
    prospect_type = profile.get("prospect_type", "")
    review_count = profile.get("review_count", 0)
    negative_pct = profile.get("negative_pct", 0.0)
    avg_rating = profile.get("avg_rating")
    top_complaints: List[Dict] = profile.get("top_complaints") or []
    sentiment_trend: List[Dict] = profile.get("sentiment_trend") or []
    real_quotes: List[Dict] = profile.get("real_quotes") or []
    scoring_breakdown: Optional[Dict] = profile.get("scoring_breakdown")
    why_now = profile.get("why_now") or ""
    erp_primary = profile.get("erp_module_primary") or "—"
    erp_secondary = profile.get("erp_module_secondary") or "—"
    data_note = profile.get("data_note") or ""

    # Header/footer with company name subtitle
    def _company_header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(DARK_HEADER)
        canvas.rect(0, PAGE_H - 45 * mm, PAGE_W, 45 * mm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 18)
        canvas.drawString(LEFT_MARGIN, PAGE_H - 18 * mm, "TEAMWILL")
        canvas.setFont("Helvetica", 13)
        canvas.drawString(LEFT_MARGIN, PAGE_H - 27 * mm, f"Company Brief — {name}")
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(SLATE_400)
        canvas.drawString(LEFT_MARGIN, PAGE_H - 34 * mm, f"{sector} · {region} · Pre-Call Intelligence Dossier")
        now_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(SLATE_400)
        canvas.drawRightString(PAGE_W - RIGHT_MARGIN, PAGE_H - 18 * mm, now_str)
        canvas.drawRightString(PAGE_W - RIGHT_MARGIN, PAGE_H - 25 * mm, "TEAMWILL AI Platform")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(SLATE_400)
        canvas.drawString(LEFT_MARGIN, 12 * mm, "Confidential \u2014 TEAMWILL Internal Use Only")
        canvas.drawRightString(PAGE_W - RIGHT_MARGIN, 12 * mm, f"Page {doc.page}")
        canvas.restoreState()

    story: list = []

    # ── Section 1: Overview ──────────────────────────────────────────────────
    story.append(Paragraph("Company Overview", section_style))

    score_str = f"{round(score)}/100" if score is not None else "N/A"
    percentile_str = f"Top {100 - round(score_percentile)}% in sector" if score_percentile is not None else ""
    rating_str = f"{avg_rating:.1f}/5" if avg_rating is not None else "N/A"

    overview_data = [
        ["Sector", sector, "Type", company_type.capitalize()],
        ["Region", region, "Country", country],
        ["Opportunity Score", score_str, "Avg Rating", rating_str],
        ["Prospect Category", prospect_type.replace("_", " ").title(), "Reviews", str(review_count)],
    ]
    if percentile_str:
        overview_data.append(["Sector Percentile", percentile_str, "Negative %", f"{negative_pct:.1f}%"])
    else:
        overview_data.append(["Negative Sentiment", f"{negative_pct:.1f}%", "ERP Fit (Primary)", erp_primary])

    ov_table = Table(overview_data, colWidths=[100, 120, 100, 120])
    ov_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTNAME", (3, 0), (3, -1), "Helvetica"),
        ("TEXTCOLOR", (0, 0), (-1, -1), SLATE_700),
        ("TEXTCOLOR", (0, 0), (0, -1), SLATE_400),
        ("TEXTCOLOR", (2, 0), (2, -1), SLATE_400),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.3, SLATE_400),
        *[("BACKGROUND", (0, r), (-1, r), SLATE_100) for r in range(0, len(overview_data), 2)],
    ]))
    story.append(ov_table)
    story.append(Spacer(1, 6))

    if why_now:
        story.append(Paragraph(f"<b>Why Now:</b> {why_now}", body_style))
        story.append(Spacer(1, 4))

    if data_note:
        story.append(Paragraph(f"<i>Note: {data_note}</i>", small_style))
        story.append(Spacer(1, 4))

    # ── Section 2: Scoring Breakdown ─────────────────────────────────────────
    if scoring_breakdown:
        story.append(Paragraph("Opportunity Scoring Breakdown", section_style))
        bd_header = ["Dimension", "Score", "Bar"]
        bd_data = [bd_header]
        labels = {
            "teamwill_fit": "TEAMWILL ERP Fit",
            "sentiment_trend": "Sentiment Trend",
            "market_presence": "Market Presence",
            "complaint_intensity": "Complaint Intensity",
        }
        for key, lbl in labels.items():
            val = scoring_breakdown.get(key, 0) or 0
            bd_data.append([lbl, f"{val:.1f}", _unicode_bar(val)])
        bd_table = Table(bd_data, colWidths=[160, 60, 100])
        bd_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), INDIGO),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("TEXTCOLOR", (0, 1), (-1, -1), SLATE_700),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.3, SLATE_400),
            *[("BACKGROUND", (0, r), (-1, r), SLATE_100) for r in range(2, len(bd_data), 2)],
        ]))
        story.append(bd_table)
        story.append(Spacer(1, 6))

    # ── Section 3: Top Complaints ─────────────────────────────────────────────
    story.append(Paragraph("Top Complaint Topics", section_style))
    if top_complaints:
        tc_header = ["Complaint Topic", "Count", "% of Reviews", "Sales Angle"]
        tc_data = [tc_header]
        for c in top_complaints[:5]:
            lbl = c.get("label", "")
            tc_data.append([
                lbl,
                str(c.get("count", 0)),
                f"{c.get('pct', 0):.1f}%",
                _get_sales_tip(lbl),
            ])
        tc_table = Table(tc_data, colWidths=[120, 40, 70, 170])
        tc_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), INDIGO),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("TEXTCOLOR", (0, 1), (-1, -1), SLATE_700),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.3, SLATE_400),
            ("WORDWRAP", (3, 1), (3, -1), 1),
            *[("BACKGROUND", (0, r), (-1, r), SLATE_100) for r in range(2, len(tc_data), 2)],
        ]))
        story.append(tc_table)
    else:
        story.append(Paragraph("No complaint data available.", body_style))
    story.append(Spacer(1, 6))

    # ── Section 4: Sentiment Trend ────────────────────────────────────────────
    if sentiment_trend:
        story.append(Paragraph("Sentiment Trend (Last 6 Months)", section_style))
        st_header = ["Month", "Negative %", "Avg Rating"]
        st_data = [st_header]
        for row in sentiment_trend[-6:]:
            m = row.get("month", "")
            yr, mo = m.split("-") if "-" in m else (m, "?")
            month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
            m_label = f"{month_names[int(mo)-1]} {yr[-2:]}" if mo.isdigit() else m
            neg = row.get("negative_pct", 0)
            rat = row.get("avg_rating")
            st_data.append([
                m_label,
                f"{neg:.1f}%",
                f"{rat:.1f}" if rat is not None else "—",
            ])
        st_table = Table(st_data, colWidths=[80, 80, 80])
        st_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), INDIGO),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("TEXTCOLOR", (0, 1), (-1, -1), SLATE_700),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.3, SLATE_400),
            *[("BACKGROUND", (0, r), (-1, r), SLATE_100) for r in range(2, len(st_data), 2)],
        ]))
        story.append(st_table)
        story.append(Spacer(1, 6))

    # ── Section 5: Voice of Customer Quotes ──────────────────────────────────
    negative_quotes = [q for q in real_quotes if q.get("sentiment") == "negative"][:3]
    if negative_quotes:
        story.append(Paragraph("Voice of Customer — Key Complaints", section_style))
        for q in negative_quotes:
            text = q.get("text", "")
            if len(text) > 220:
                text = text[:217] + "\u2026"
            rating = q.get("rating")
            date = q.get("date", "")
            date_str = ""
            if date:
                try:
                    date_str = datetime.fromisoformat(date[:10]).strftime("%b %Y")
                except Exception:
                    date_str = date[:7]
            meta = f"Rating: {rating}/5 · {date_str}" if rating else date_str
            story.append(Paragraph(f'\u201c{text}\u201d', body_style))
            if meta:
                story.append(Paragraph(meta, small_style))
            story.append(Spacer(1, 5))

    # ── Section 6: ERP Fit + Opening Line ────────────────────────────────────
    story.append(Paragraph("TEAMWILL ERP Fit", section_style))
    erp_data = [
        ["Primary Module", erp_primary],
        ["Secondary Module", erp_secondary],
    ]
    erp_table = Table(erp_data, colWidths=[140, 200])
    erp_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), SLATE_400),
        ("TEXTCOLOR", (1, 0), (1, -1), SLATE_700),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.3, SLATE_400),
        ("BACKGROUND", (0, 0), (-1, 0), SLATE_100),
    ]))
    story.append(erp_table)
    story.append(Spacer(1, 8))

    top_complaint_label = top_complaints[0].get("label", "operational challenges") if top_complaints else "operational challenges"
    opening_line = (
        f"We noticed companies in the {sector.lower()} sector are increasingly struggling with "
        f"{top_complaint_label.lower()} \u2014 is that something your team has been dealing with?"
    )
    story.append(Paragraph("<b>Suggested Opening Line:</b>", label_style))
    story.append(Paragraph(f'\u201c{opening_line}\u201d', body_style))

    # ── Build PDF ─────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    content_frame = Frame(
        LEFT_MARGIN,
        BOT_MARGIN,
        PAGE_W - LEFT_MARGIN - RIGHT_MARGIN,
        PAGE_H - TOP_MARGIN - BOT_MARGIN - 30 * mm,
        id="main",
    )
    page_tmpl = PageTemplate(id="company", frames=[content_frame], onPage=_company_header_footer)
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        pageTemplates=[page_tmpl],
        title=f"TEAMWILL — {name} Company Brief",
        author="TEAMWILL AI Platform",
    )
    doc.build(story)
    buf.seek(0)
    pdf_bytes = buf.read()
    logger.info("Company brief PDF generated for %s: %d bytes", name, len(pdf_bytes))
    return pdf_bytes


def _get_sales_tip(label: str) -> str:
    lower = label.lower()
    if "service" in lower or "customer" in lower:
        return "Ask about their customer service workflow"
    if "billing" in lower or "pricing" in lower or "policy" in lower:
        return "Ask about their invoicing & billing process"
    if "claim" in lower:
        return "Ask about their claims processing system"
    if "wait" in lower or "response" in lower or "time" in lower:
        return "Ask about their response-time management"
    if "reliab" in lower or "quality" in lower:
        return "Ask about their quality control systems"
    if "staff" in lower or "commun" in lower:
        return "Ask about their team coordination tools"
    return "Explore their current operational workflow"
