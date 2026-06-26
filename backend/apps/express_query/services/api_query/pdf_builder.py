"""将快递鸟查询结果渲染为 PDF。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _register_chinese_font() -> str:
    """注册中文字体，返回可用的字体名称。"""
    font_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in font_paths:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont("ChineseFont", path))
                return "ChineseFont"
            except Exception:
                continue
    return "Helvetica"


def build_tracking_pdf(
    output_path: Path,
    tracking_number: str,
    carrier_code: str,
    traces: list[dict[str, Any]],
    state: str = "",
    query_time: str = "",
) -> None:
    """
    生成快递查询结果 PDF。

    Args:
        output_path: 输出 PDF 路径
        tracking_number: 运单号
        carrier_code: 快递公司编码
        traces: 轨迹列表 [{AcceptTime, AcceptStation, Location}]
        state: 物流状态
        query_time: 查询时间
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    font_name = _register_chinese_font()
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CNTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=16,
        spaceAfter=6 * mm,
    )
    normal_style = ParagraphStyle(
        "CNNormal",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        leading=14,
    )
    small_style = ParagraphStyle(
        "CNSmall",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8,
        leading=11,
        textColor=colors.grey,
    )

    now_str = query_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state_map = {
        "0": "在途",
        "1": "揽收",
        "2": "疑难",
        "3": "签收",
        "4": "退签",
        "5": "派件",
        "8": "清关",
        "14": "拒签",
    }
    state_label = state_map.get(str(state), str(state) or "未知")

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=15 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    story: list = []

    # 标题
    story.append(Paragraph("快递查询结果", title_style))

    # 基本信息表
    info_data = [
        ["运单号", tracking_number],
        ["快递公司", carrier_code.upper()],
        ["物流状态", state_label],
        ["查询时间", now_str],
    ]
    info_table = Table(info_data, colWidths=[80, 300])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("RIGHTPADDING", (0, 0), (0, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 8 * mm))

    # 轨迹列表
    if traces:
        story.append(Paragraph("物流轨迹", ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading2"],
            fontName=font_name,
            fontSize=13,
            spaceAfter=4 * mm,
        )))

        trace_data = [["时间", "轨迹信息", "地点"]]
        for t in reversed(traces):  # 最新在前
            trace_data.append([
                t.get("AcceptTime", ""),
                t.get("AcceptStation", ""),
                t.get("Location", ""),
            ])

        trace_table = Table(trace_data, colWidths=[120, 260, 80])
        trace_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#333333")),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(trace_table)
    else:
        story.append(Paragraph("暂无轨迹信息", normal_style))

    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        f"数据来源：快递鸟 API | 生成时间：{now_str}",
        small_style,
    ))

    doc.build(story)
