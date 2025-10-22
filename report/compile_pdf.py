"""PDF compilation utilities with badge support and cue highlighting."""
from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Any, Dict, Iterable, List

from retrieval.evidence_rag import CLAIM_CUES, TRL_CUES

try:  # pragma: no cover - optional dependency
    from reportlab.lib.pagesizes import A4  # type: ignore
    from reportlab.pdfbase import pdfmetrics  # type: ignore
    from reportlab.pdfbase.ttfonts import TTFont  # type: ignore
    from reportlab.pdfgen import canvas  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    A4 = None  # type: ignore
    canvas = None  # type: ignore

CUE_WORDS = {cue.lower() for cue in (*TRL_CUES, *CLAIM_CUES)}
DEFAULT_FONT = "Helvetica"
DEFAULT_FONT_BOLD = "Helvetica-Bold"
FALLBACK_NOTE = "Rendered with default font. Install NotoSansCJK for improved CJK coverage."
DISCLAIMER_TEXT = "본 결과는 자동 분석으로 법률 자문이 아닙니다."


def _register_font() -> str:
    if canvas is None:
        return DEFAULT_FONT
    font_path = Path("fonts") / "NotoSansCJK-Regular.ttc"
    if font_path.exists():
        try:
            pdfmetrics.registerFont(TTFont("NotoSansCJK", str(font_path)))
            return "NotoSansCJK"
        except Exception:  # pragma: no cover - font registration failure
            return DEFAULT_FONT
    return DEFAULT_FONT


def _format_badge(badge: str) -> str:
    return f"[{badge}]"


def _draw_highlighted_line(
    canvas_obj: Any,
    line: str,
    x: float,
    y: float,
    max_width: float,
    font_regular: str,
    font_bold: str,
    font_size: int,
) -> float:
    tokens = re.split(r"(\W+)", line)
    cursor = x
    for token in tokens:
        if not token:
            continue
        token_lower = token.lower()
        font_name = font_bold if token_lower in CUE_WORDS else font_regular
        token_width = canvas_obj.stringWidth(token, font_name, font_size)
        if cursor + token_width > x + max_width:
            y -= font_size + 2
            cursor = x
        canvas_obj.setFont(font_name, font_size)
        canvas_obj.drawString(cursor, y, token)
        cursor += token_width
    return y - (font_size + 4)


def _render_pdf(report_payload: Dict[str, Any], report_path: Path) -> None:
    font_regular = _register_font()
    font_bold = DEFAULT_FONT_BOLD if font_regular == DEFAULT_FONT else font_regular

    canvas_obj = canvas.Canvas(str(report_path), pagesize=A4)  # type: ignore[arg-type]
    page_width, page_height = A4  # type: ignore[assignment]

    y = page_height - 60
    canvas_obj.setFont(font_bold, 18)
    canvas_obj.drawString(40, y, "Edge AI Patent Assessment")
    canvas_obj.setFont(font_regular, 9)
    canvas_obj.drawString(40, y - 16, FALLBACK_NOTE)
    y -= 40

    summary = report_payload.get("summary", {})
    total = summary.get("total")
    label = summary.get("label", "N/A")
    flags = ", ".join(summary.get("flags", [])) or "None"

    canvas_obj.setFont(font_regular, 12)
    total_line = f"Total Score: {total:.2f}" if isinstance(total, (int, float)) else "Total Score: N/A"
    canvas_obj.drawString(40, y, total_line)
    y -= 18
    canvas_obj.drawString(40, y, f"Label: {label}")
    y -= 18
    canvas_obj.drawString(40, y, f"Flags: {flags}")
    y -= 24

    synthesis = report_payload.get("synthesis", {})
    summary_text = synthesis.get("ps_e_summary")
    if summary_text:
        canvas_obj.setFont(font_bold, 14)
        canvas_obj.drawString(40, y, "Synthesis")
        y -= 20
        canvas_obj.setFont(font_regular, 11)
        for line in textwrap.wrap(summary_text, width=90):
            canvas_obj.drawString(45, y, line)
            y -= 14
            if y < 140:
                canvas_obj.showPage()
                page_width, page_height = A4  # type: ignore[assignment]
                y = page_height - 60
                canvas_obj.setFont(font_regular, 11)
        y -= 16

    api_metrics = report_payload.get("api_metrics", {})
    if api_metrics:
        canvas_obj.setFont(font_bold, 14)
        canvas_obj.drawString(40, y, "API Metrics")
        y -= 20
        canvas_obj.setFont(font_regular, 11)
        for metric, value in sorted(api_metrics.items()):
            display_value = ", ".join(value) if isinstance(value, list) else value
            canvas_obj.drawString(45, y, f"{metric}: {display_value}")
            y -= 14
            if y < 140:
                canvas_obj.showPage()
                page_width, page_height = A4  # type: ignore[assignment]
                y = page_height - 60
                canvas_obj.setFont(font_regular, 11)
        y -= 16

    metadata = report_payload.get("metadata", {})
    badges = metadata.get("source_badges", {})
    max_snippets = metadata.get("max_snippets_per_metric", 3)

    canvas_obj.setFont(font_bold, 14)
    canvas_obj.drawString(40, y, "Score Breakdown")
    y -= 24
    canvas_obj.setFont(font_regular, 11)
    scores = report_payload.get("scores", {})
    for metric, value in scores.items():
        badge = _format_badge(badges.get(metric, "N/A"))
        value_text = "N/A" if value is None else f"{float(value):.2f}"
        canvas_obj.drawString(45, y, f"{metric:<12} {value_text:>8} {badge}")
        y -= 16
        if y < 140:
            canvas_obj.showPage()
            y = page_height - 60
            canvas_obj.setFont(font_regular, 11)

    y -= 8
    evidence = report_payload.get("evidence", {})
    for category, payload in evidence.items():
        if y < 200:
            canvas_obj.showPage()
            y = page_height - 60

        canvas_obj.setFont(font_bold, 14)
        badge = _format_badge(badges.get(category, "Local RAG"))
        canvas_obj.drawString(40, y, f"Evidence - {category.upper()} {badge}")
        y -= 20

        canvas_obj.setFont(font_regular, 11)
        if category == "trl":
            level = payload.get("level")
            canvas_obj.drawString(45, y, f"Estimated TRL Level: {level if level is not None else 'N/A'}")
            y -= 18
        if category == "claims":
            avg_tokens = payload.get("avg_len_tokens") or 0.0
            info_line = f"Independent claims: {payload.get('num_independent', 'N/A')}, Avg tokens: {avg_tokens:.1f}"
            canvas_obj.drawString(45, y, info_line)
            y -= 18

        snippets: Iterable[Dict[str, Any]] = payload.get("snippets", [])
        for idx, snippet in enumerate(snippets, start=1):
            if idx > max_snippets:
                break
            snippet_text = snippet.get("text", "")
            canvas_obj.setFont(font_bold, 11)
            canvas_obj.drawString(45, y, f"{idx}.")
            y -= 14
            y = _draw_highlighted_line(
                canvas_obj,
                snippet_text,
                x=60,
                y=y,
                max_width=page_width - 120,
                font_regular=font_regular,
                font_bold=font_bold,
                font_size=11,
            )
            if y < 120:
                canvas_obj.showPage()
                y = page_height - 60

        y -= 10

    if y < 120:
        canvas_obj.showPage()

    canvas_obj.setFont(font_regular, 10)
    canvas_obj.drawString(40, 60, DISCLAIMER_TEXT)
    canvas_obj.save()


def _highlight_text(text: str) -> str:
    def replacer(match: re.Match[str]) -> str:
        word = match.group(0)
        return f"**{word}**" if word.lower() in CUE_WORDS else word

    return re.sub(r"\b\w+\b", replacer, text)


def _render_text(report_payload: Dict[str, Any], report_path: Path) -> None:
    lines: List[str] = []
    summary = report_payload.get("summary", {})
    badges = report_payload.get("metadata", {}).get("source_badges", {})
    max_snippets = report_payload.get("metadata", {}).get("max_snippets_per_metric", 3)

    lines.append("Edge AI Patent Assessment (text fallback)")
    lines.append(FALLBACK_NOTE)
    lines.append("")
    total = summary.get("total")
    total_line = f"Total Score: {total:.2f}" if isinstance(total, (int, float)) else "Total Score: N/A"
    lines.append(total_line)
    lines.append(f"Label: {summary.get('label', 'N/A')}")
    lines.append(f"Flags: {', '.join(summary.get('flags', [])) or 'None'}")
    lines.append("")
    synthesis = report_payload.get("synthesis", {})
    if synthesis.get("ps_e_summary"):
        lines.append("Synthesis")
        lines.append(f"  {synthesis['ps_e_summary']}")
        lines.append("")
    api_metrics = report_payload.get("api_metrics", {})
    if api_metrics:
        lines.append("API Metrics")
        for metric, value in sorted(api_metrics.items()):
            display_value = ", ".join(value) if isinstance(value, list) else value
            lines.append(f"  {metric}: {display_value}")
        lines.append("")
    lines.append("Score Breakdown")
    for metric, value in report_payload.get("scores", {}).items():
        badge = _format_badge(badges.get(metric, "N/A"))
        value_text = "N/A" if value is None else f"{float(value):.2f}"
        lines.append(f"- {metric}: {value_text} {badge}")
    lines.append("")
    lines.append("Evidence")
    for category, payload in report_payload.get("evidence", {}).items():
        badge = _format_badge(badges.get(category, "Local RAG"))
        lines.append(f"[{category.upper()}] {badge}")
        if category == "trl":
            lines.append(f"  Estimated TRL Level: {payload.get('level', 'N/A')}")
        if category == "claims":
            avg_tokens = payload.get("avg_len_tokens") or 0.0
            lines.append(f"  Independent claims: {payload.get('num_independent', 'N/A')}, Avg tokens: {avg_tokens:.1f}")
        for idx, snippet in enumerate(payload.get("snippets", [])[:max_snippets], start=1):
            lines.append(f"  {idx}. {_highlight_text(snippet.get('text', ''))}")
        lines.append("")
    lines.append(DISCLAIMER_TEXT)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def compile_report_pdf(report_payload: Dict[str, Any]) -> str:
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    metadata = report_payload.get("metadata", {})
    timestamp = metadata.get("timestamp") or "unknown"
    safe_ts = "".join(char for char in timestamp if char.isdigit()) or "000000"
    report_payload.setdefault("metadata", {})["max_snippets_per_metric"] = metadata.get("max_snippets_per_metric", 3)

    pdf_path = reports_dir / f"report_{safe_ts}.pdf"
    if canvas is not None and A4 is not None:
        try:
            _render_pdf(report_payload, pdf_path)
            return str(pdf_path)
        except Exception:  # pragma: no cover - fallback on rendering failure
            pdf_path.unlink(missing_ok=True)

    text_path = reports_dir / f"report_{safe_ts}.txt"
    _render_text(report_payload, text_path)
    return str(text_path)


__all__ = ["compile_report_pdf"]
