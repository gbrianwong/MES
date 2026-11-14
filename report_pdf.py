"""Create PDF production reports for the MES HMI."""

from __future__ import annotations

import time
from typing import Sequence
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Table,
    TableStyle,
)

from mes import LineData
from prod import BallPen


def _cell(value: object, style: ParagraphStyle) -> Paragraph:
    text = str(value)
    try:
        text.encode("cp1252")
    except UnicodeEncodeError:
        text = text.encode("ascii", "backslashreplace").decode("ascii")
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _table(rows: list[list[Paragraph]], widths: list[float]) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d1b2a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#b8c2cc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#edf2f7")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def generate_pdf_report(
    path: str,
    line_data: Sequence[LineData],
    rejections: Sequence[dict[str, str]],
    genealogy: Sequence[BallPen],
) -> None:
    """Write current work-order totals, rejection details, and shipped-pen traces."""
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=17, leading=21, textColor=colors.HexColor("#0d1b2a"),
        alignment=TA_CENTER, spaceAfter=5 * mm,
    )
    section_style = ParagraphStyle(
        "ReportSection", parent=styles["Heading2"], fontSize=11, leading=14,
        textColor=colors.HexColor("#146078"), spaceBefore=5 * mm, spaceAfter=2 * mm,
    )
    cell_style = ParagraphStyle(
        "ReportCell", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=7, leading=9, spaceAfter=0,
    )
    header_style = ParagraphStyle(
        "ReportHeader", parent=cell_style, fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    def cells(values: Sequence[object], style: ParagraphStyle) -> list[Paragraph]:
        return [_cell(value, style) for value in values]

    story = [
        Paragraph("Ball Pen MES — Production Report", title_style),
        Paragraph(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}", cell_style),
        Paragraph("Production by Work Order", section_style),
    ]

    summary = [cells(
        ("Order #", "Work Order", "Target", "Produced", "Rejected", "Yield", "Status"),
        header_style,
    )]
    for data in line_data:
        summary.append(cells((
            data.order_number,
            data.name,
            data.target,
            data.produced,
            data.rejected,
            f"{data.yield_pct()}%",
            data.status.name,
        ), cell_style))
    if len(summary) == 1:
        summary.append([_cell("No work orders configured.", cell_style)] + [
            _cell("", cell_style) for _ in range(6)
        ])
    story.append(_table(summary, [48, 190, 48, 58, 58, 48, 62]))

    story.append(Paragraph("Rejections", section_style))
    rejection_rows = [cells(
        ("Order #", "Work Order", "Item", "Station", "Reason"),
        header_style,
    )]
    for rejection in rejections:
        rejection_rows.append(cells((
            rejection["order_number"],
            rejection["order_name"],
            rejection["item"],
            rejection["station"],
            rejection["reason"],
        ), cell_style))
    if len(rejection_rows) == 1:
        rejection_rows.append([_cell("No rejections recorded.", cell_style)] + [
            _cell("", cell_style) for _ in range(4)
        ])
    story.append(_table(rejection_rows, [48, 130, 130, 120, 220]))

    story.append(Paragraph("Genealogy &amp; Traceability — Shipped Pens", section_style))
    genealogy_rows = [cells(
        ("Pen #", "Component", "Part #", "Variant", "Machine",
         "Pen Timestamp", "Part Timestamp", "Order #"),
        header_style,
    )]
    for pen in genealogy:
        for component_name, component in pen.components.items():
            genealogy_rows.append(cells((
                pen.serial,
                component_name.capitalize(),
                component.serial,
                component.variant or "—",
                component.machine or "—",
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(pen.timestamp)),
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(component.timestamp)),
                pen.order_number,
            ), cell_style))
    if len(genealogy_rows) == 1:
        genealogy_rows.append([_cell("No shipped pens recorded.", cell_style)] + [
            _cell("", cell_style) for _ in range(7)
        ])
    story.append(_table(genealogy_rows, [42, 60, 45, 105, 95, 120, 120, 50]))

    def add_page_number(canvas, document) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#52616f"))
        canvas.drawRightString(
            landscape(A4)[0] - 15 * mm, 9 * mm, f"Page {document.page}",
        )
        canvas.restoreState()

    document = SimpleDocTemplate(
        path,
        pagesize=landscape(A4),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="Ball Pen MES Production Report",
    )
    document.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
