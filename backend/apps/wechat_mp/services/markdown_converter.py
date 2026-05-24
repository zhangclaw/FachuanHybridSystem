"""Markdown → 公众号 HTML 转换服务。

输出内联样式的 HTML，可直接通过剪贴板粘贴到公众号 ProseMirror 编辑器。
"""

from __future__ import annotations

import logging
import re

import markdown  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# 公众号支持的内联样式（直接写在元素上）
_INLINE_STYLES: dict[str, str] = {
    "section": "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.8;color:#333;",
    "h1": "font-size:22px;font-weight:bold;color:#1a1a1a;margin:28px 0 14px;padding-bottom:10px;border-bottom:2px solid #07c160;",
    "h2": "font-size:20px;font-weight:bold;color:#1a1a1a;margin:24px 0 12px;padding-bottom:8px;border-bottom:2px solid #07c160;",
    "h3": "font-size:17px;font-weight:bold;color:#333;margin:20px 0 10px;",
    "h4": "font-size:15px;font-weight:bold;color:#333;margin:16px 0 8px;",
    "p": "font-size:15px;margin:10px 0;text-align:justify;line-height:1.8;letter-spacing:0.5px;",
    "strong": "color:#07c160;font-weight:bold;",
    "em": "font-style:italic;color:#666;",
    "blockquote": "border-left:4px solid #07c160;padding:10px 15px;margin:15px 0;background:#f8f8f8;color:#666;font-size:14px;",
    "ul": "padding-left:20px;margin:10px 0;",
    "ol": "padding-left:20px;margin:10px 0;",
    "li": "font-size:15px;margin:5px 0;line-height:1.8;",
    "code": "background:#f4f4f4;padding:2px 6px;border-radius:3px;font-size:14px;color:#c7254e;font-family:Consolas,Monaco,monospace;",
    "pre": "background:#f4f4f4;padding:15px;border-radius:5px;overflow-x:auto;margin:15px 0;font-size:13px;line-height:1.5;",
    "hr": "border:none;border-top:1px solid #eee;margin:20px 0;",
    "img": "max-width:100%;height:auto;border-radius:4px;",
    "table": "width:100%;border-collapse:collapse;margin:15px 0;font-size:14px;",
    "th": "border:1px solid #ddd;padding:8px 12px;text-align:left;background:#f4f4f4;font-weight:bold;",
    "td": "border:1px solid #ddd;padding:8px 12px;text-align:left;",
    "a": "color:#576b95;text-decoration:none;",
}


def _apply_inline_styles(html: str) -> str:
    """将内联样式应用到 HTML 元素上。"""
    for tag, style in _INLINE_STYLES.items():
        # 匹配 <tag> 或 <tag ...>，但不重复添加 style
        pattern = rf"<{tag}(?![^>]*style=)(\s|>)"
        replacement = f'<{tag} style="{style}"\\1'
        html = re.sub(pattern, replacement, html)
    return html


def _wrap_section(html: str) -> str:
    """用 section 包裹 HTML 并添加全局样式。"""
    return f'<section style="{_INLINE_STYLES["section"]}">{html}</section>'


def convert_markdown_to_wechat_html(md_content: str) -> str:
    """将 Markdown 转换为公众号支持的内联样式 HTML。

    输出的 HTML 可直接通过剪贴板粘贴到公众号 ProseMirror 编辑器。

    Args:
        md_content: Markdown 格式的文本

    Returns:
        内联样式的 HTML 字符串
    """
    # 移除第一行标题（公众号标题单独设置）
    lines = md_content.strip().split("\n")
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    md_content = "\n".join(lines).strip()

    # 转换 Markdown → HTML
    html = markdown.markdown(
        md_content,
        extensions=[
            "markdown.extensions.tables",
            "markdown.extensions.fenced_code",
            "markdown.extensions.codehilite",
        ],
        extension_configs={
            "markdown.extensions.codehilite": {
                "css_class": "highlight",
                "noclasses": True,
            },
        },
    )

    # 应用内联样式
    html = _apply_inline_styles(html)

    # 用 section 包裹
    html = _wrap_section(html)

    return html


def extract_summary(md_content: str, max_length: int = 120) -> str:
    """从 Markdown 内容中提取摘要（用于公众号文章摘要）。"""
    # 移除标题行
    lines = md_content.strip().split("\n")
    text_lines = [line for line in lines if not line.startswith("#")]

    # 移除 Markdown 标记
    text = " ".join(text_lines)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    text = re.sub(r"#{1,6}\s+", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > max_length:
        text = text[:max_length] + "..."

    return text
