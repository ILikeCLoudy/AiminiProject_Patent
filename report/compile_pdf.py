"""PDF compilation utilities for Edge AI patent assessment reports."""
from __future__ import annotations

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
DISCLAIMER_TEXT = "This report is generated automatically and does not constitute legal advice."

if A4 is not None:
    PAGE_WIDTH, PAGE_HEIGHT = A4
else:
    PAGE_WIDTH, PAGE_HEIGHT = (595.27, 841.89)


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


def _draw_wrapped(
    canvas_obj: Any,
    text: str,
    *,
    x: float,
    y: float,
    width: float,
    font: str,
    font_size: int,
) -> float:
    canvas_obj.setFont(font, font_size)
    for line in textwrap.wrap(text, width=width):
        canvas_obj.drawString(x, y, line)
        y -= font_size + 2
    return y


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
    tokens = line.split()
    cursor = x
    for token in tokens:
        token_display = token + " "
        font_name = font_bold if token.lower() in CUE_WORDS else font_regular
        token_width = canvas_obj.stringWidth(token_display, font_name, font_size)
        if cursor + token_width > x + max_width:
            y -= font_size + 2
            cursor = x
        canvas_obj.setFont(font_name, font_size)
        canvas_obj.drawString(cursor, y, token_display)
        cursor += token_width
    return y - (font_size + 4)


def _render_summary(canvas_obj: Any, summary_card: Dict[str, Any], *, font_regular: str, font_bold: str, y: float) -> float:
    canvas_obj.setFont(font_bold, 14)
    canvas_obj.drawString(40, y, "SUMMARY")
    y -= 24
    canvas_obj.setFont(font_regular, 11)
    y = _draw_wrapped(canvas_obj, f"Conclusion: {summary_card.get('conclusion', 'N/A')}", x=45, y=y, width=90, font=font_regular, font_size=11)
    reasons = " / ".join(summary_card.get("reasons", []))
    y = _draw_wrapped(canvas_obj, f"Key reasons: {reasons or 'N/A'}", x=45, y=y, width=90, font=font_regular, font_size=11)
    scope = summary_card.get("purpose_scope", {}).get("scope", {})
    scope_line = (
        f"Purpose: {summary_card.get('purpose_scope', {}).get('purpose', 'N/A')} | "
        f"Keywords {scope.get('keywords', '')} | CPC {scope.get('cpc', '')} | Period {scope.get('period', '')}"
    )
    y = _draw_wrapped(canvas_obj, scope_line, x=45, y=y, width=90, font=font_regular, font_size=11)
    top_line = summary_card.get("top_line", {})
    topline_text = (
        f"Top-line: N={top_line.get('documents', 'N/A')} / M={top_line.get('family_size', 'N/A')} / "
        f"K={top_line.get('country_count', 'N/A')} | Label {top_line.get('label', 'N/A')}"
    )
    y = _draw_wrapped(canvas_obj, topline_text, x=45, y=y, width=90, font=font_regular, font_size=11)
    y -= 6
    canvas_obj.setFont(font_bold, 12)
    canvas_obj.drawString(45, y, "Recommendations")
    y -= 16
    canvas_obj.setFont(font_regular, 11)
    for action in summary_card.get("actions", []):
        text = f"- {action.get('action')} (owner {action.get('owner')}, due {action.get('due')}): {action.get('note')}"
        y = _draw_wrapped(canvas_obj, text, x=55, y=y, width=88, font=font_regular, font_size=11)
    y -= 6
    canvas_obj.setFont(font_bold, 12)
    canvas_obj.drawString(45, y, "Risks")
    y -= 16
    canvas_obj.setFont(font_regular, 11)
    for risk in summary_card.get("risks", []):
        text = f"- {risk.get('item')}: {risk.get('impact')}"
        y = _draw_wrapped(canvas_obj, text, x=55, y=y, width=88, font=font_regular, font_size=11)
    trust = summary_card.get("trust_meta", {})
    trust_line = (
        f"Trust meta: missing {trust.get('missing_ratio', 0.0)*100:.1f}% | "
        f"Executed {trust.get('timestamp', 'N/A')} | Policy {trust.get('policy_version', 'N/A')}"
    )
    y = _draw_wrapped(canvas_obj, trust_line, x=55, y=y - 10, width=88, font=font_regular, font_size=11)
    return y


def _render_main_body(canvas_obj: Any, main_body: Dict[str, Any], *, font_regular: str, font_bold: str, y: float) -> float:
    if y < 200:
        canvas_obj.showPage()
        y = PAGE_HEIGHT - 60
    canvas_obj.setFont(font_bold, 14)
    canvas_obj.drawString(40, y, "MAIN BODY")
    y -= 24
    sections = [
        ("1. Scope & Method", main_body.get("scope_method")),
        ("2. Dataset Overview", main_body.get("dataset")),
        ("3. Core Metrics", main_body.get("core_metrics")),
        ("4. Edge Fitness", main_body.get("edge_fitness")),
        ("5. Competitive & Standards", main_body.get("competitive")),
        ("6. Risk Profile", main_body.get("risk_profile")),
        ("7. Ranking & Labelling", main_body.get("ranking")),
        ("8. Decision Cards", main_body.get("candidate_cards")),
        ("9. Conclusion", main_body.get("conclusion")),
    ]
    for title, payload in sections:
        if y < 160:
            canvas_obj.showPage()
            y = PAGE_HEIGHT - 60
        canvas_obj.setFont(font_bold, 12)
        canvas_obj.drawString(45, y, title)
        y -= 16
        canvas_obj.setFont(font_regular, 11)
        if isinstance(payload, dict):
            for key, value in payload.items():
                if value in (None, "", []):
                    continue
                if isinstance(value, list):
                    text = f"- {key}: {', '.join(map(str, value))}"
                else:
                    text = f"- {key}: {value}"
                y = _draw_wrapped(canvas_obj, text, x=55, y=y, width=88, font=font_regular, font_size=11)
        elif isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    text = "; ".join(f"{k}={v}" for k, v in item.items() if v not in (None, ""))
                else:
                    text = str(item)
                y = _draw_wrapped(canvas_obj, f"- {text}", x=55, y=y, width=88, font=font_regular, font_size=11)
        elif payload:
            y = _draw_wrapped(canvas_obj, f"- {payload}", x=55, y=y, width=88, font=font_regular, font_size=11)
        y -= 6
    return y


def _render_references(canvas_obj: Any, references: List[Dict[str, Any]], *, font_regular: str, font_bold: str, y: float) -> float:
    if not references:
        return y
    if y < 160:
        canvas_obj.showPage()
        y = PAGE_HEIGHT - 60
    canvas_obj.setFont(font_bold, 14)
    canvas_obj.drawString(40, y, "REFERENCE")
    y -= 20
    canvas_obj.setFont(font_regular, 11)
    for idx, ref in enumerate(references, start=1):
        text = f"[R{idx}] {ref.get('source')} - {ref.get('url')}"
        y = _draw_wrapped(canvas_obj, text, x=45, y=y, width=90, font=font_regular, font_size=11)
    y -= 6
    return y


def _render_appendix(canvas_obj: Any, appendix: Dict[str, Any], *, font_regular: str, font_bold: str, y: float) -> float:
    if not appendix:
        return y
    if y < 160:
        canvas_obj.showPage()
        y = PAGE_HEIGHT - 60
    canvas_obj.setFont(font_bold, 14)
    canvas_obj.drawString(40, y, "APPENDIX")
    y -= 20
    canvas_obj.setFont(font_regular, 11)
    for key, value in appendix.items():
        if isinstance(value, dict):
            text = f"{key}: " + ", ".join(f"{k}={v}" for k, v in value.items())
        else:
            text = f"{key}: {value}"
        y = _draw_wrapped(canvas_obj, text, x=45, y=y, width=90, font=font_regular, font_size=11)
    y -= 6
    return y


def _render_evidence(canvas_obj: Any, evidence: Dict[str, Any], metadata: Dict[str, Any], *, font_regular: str, font_bold: str, y: float) -> float:
    if not evidence:
        return y
    badges = metadata.get("source_badges", {})
    max_snippets = metadata.get("max_snippets_per_metric", 3)
    if y < 180:
        canvas_obj.showPage()
        y = PAGE_HEIGHT - 60
    canvas_obj.setFont(font_bold, 14)
    canvas_obj.drawString(40, y, "EVIDENCE")
    y -= 24
    for category, payload in evidence.items():
        if y < 140:
            canvas_obj.showPage()
            y = PAGE_HEIGHT - 60
        badge = _format_badge(badges.get(category, "Local RAG"))
        canvas_obj.setFont(font_bold, 12)
        canvas_obj.drawString(45, y, f"{category.upper()} {badge}")
        y -= 16
        canvas_obj.setFont(font_regular, 11)
        if category == "trl":
            level = payload.get("level")
            y = _draw_wrapped(canvas_obj, f"TRL level: {level if level is not None else 'N/A'}", x=55, y=y, width=88, font=font_regular, font_size=11)
        if category == "claims":
            avg_tokens = payload.get("avg_len_tokens") or 0.0
            y = _draw_wrapped(canvas_obj, f"Independent claims: {payload.get('num_independent', 'N/A')}, Avg tokens: {avg_tokens:.1f}", x=55, y=y, width=88, font=font_regular, font_size=11)
        snippets: Iterable[Dict[str, Any]] = payload.get("snippets", [])
        for idx, snippet in enumerate(snippets, start=1):
            if idx > max_snippets:
                break
            snippet_text = snippet.get("text", "")
            y = _draw_highlighted_line(
                canvas_obj,
                snippet_text,
                x=60,
                y=y,
                max_width=PAGE_WIDTH - 120,
                font_regular=font_regular,
                font_bold=font_bold,
                font_size=11,
            )
            if y < 120:
                canvas_obj.showPage()
                y = PAGE_HEIGHT - 60
        y -= 10
    return y


def _render_pdf(report_payload: Dict[str, Any], report_path: Path) -> None:
    font_regular = _register_font()
    font_bold = DEFAULT_FONT_BOLD if font_regular == DEFAULT_FONT else font_regular

    if canvas is None or A4 is None:
        raise RuntimeError("reportlab is required for PDF rendering")

    canvas_obj = canvas.Canvas(str(report_path), pagesize=A4)  # type: ignore[arg-type]

    y = PAGE_HEIGHT - 60
    canvas_obj.setFont(font_bold, 18)
    canvas_obj.drawString(40, y, "Edge AI Patent Assessment")
    canvas_obj.setFont(font_regular, 9)
    canvas_obj.drawString(40, y - 16, FALLBACK_NOTE)
    y -= 40

    summary_card = report_payload.get("summary_card")
    if summary_card:
        y = _render_summary(canvas_obj, summary_card, font_regular=font_regular, font_bold=font_bold, y=y)

    main_body = report_payload.get("main_body", {})
    if main_body:
        y = _render_main_body(canvas_obj, main_body, font_regular=font_regular, font_bold=font_bold, y=y)

    references = report_payload.get("references", [])
    y = _render_references(canvas_obj, references, font_regular=font_regular, font_bold=font_bold, y=y)

    appendix = report_payload.get("appendix", {})
    y = _render_appendix(canvas_obj, appendix, font_regular=font_regular, font_bold=font_bold, y=y)

    metadata = report_payload.get("metadata", {})
    evidence = report_payload.get("evidence", {})
    y = _render_evidence(canvas_obj, evidence, metadata, font_regular=font_regular, font_bold=font_bold, y=y)

    canvas_obj.setFont(font_regular, 10)
    canvas_obj.drawString(40, 60, DISCLAIMER_TEXT)
    canvas_obj.save()


def _render_text(report_payload: Dict[str, Any], report_path: Path) -> None:
    lines: List[str] = []
    summary_card = report_payload.get("summary_card")
    decision = report_payload.get("decision", {})
    metadata = report_payload.get("metadata", {})
    badges = metadata.get("source_badges", {})
    max_snippets = metadata.get("max_snippets_per_metric", 3)

    lines.append("Edge AI Patent Assessment (text fallback)")
    lines.append(FALLBACK_NOTE)
    lines.append("")

    if summary_card:
        lines.append(f"Conclusion: {summary_card.get('conclusion', 'N/A')}")
        lines.append(f"Key reasons: {' / '.join(summary_card.get('reasons', []))}")
        scope = summary_card.get("purpose_scope", {}).get("scope", {})
        lines.append(
            f"Purpose: {summary_card.get('purpose_scope', {}).get('purpose', 'N/A')} | "
            f"Keywords {scope.get('keywords', '')} | CPC {scope.get('cpc', '')} | Period {scope.get('period', '')}"
        )
        top_line = summary_card.get("top_line", {})
        lines.append(
            f"Top-line: N={top_line.get('documents', 'N/A')} / M={top_line.get('family_size', 'N/A')} / "
            f"K={top_line.get('country_count', 'N/A')} | Label {top_line.get('label', 'N/A')}"
        )
        lines.append("Recommendations:")
        for action in summary_card.get("actions", []):
            lines.append(
                f"- {action.get('action')} (owner {action.get('owner')}, due {action.get('due')}): {action.get('note')}"
            )
        lines.append("Risks:")
        for risk in summary_card.get("risks", []):
            lines.append(f"- {risk.get('item')}: {risk.get('impact')}")
        trust = summary_card.get("trust_meta", {})
        lines.append(
            f"Trust meta: missing {trust.get('missing_ratio', 0.0)*100:.1f}% | executed {trust.get('timestamp', 'N/A')} | "
            f"policy {trust.get('policy_version', 'N/A')}"
        )
    else:
        total = decision.get("total")
        total_line = f"Total Score: {total:.2f}" if isinstance(total, (int, float)) else "Total Score: N/A"
        lines.append(total_line)
        lines.append(f"Label: {decision.get('label', 'N/A')}")
        lines.append(f"Flags: {', '.join(decision.get('flags', [])) or 'None'}")

    lines.append("")
    lines.append("MAIN BODY")
    main_body = report_payload.get("main_body", {})
    for title, payload in [
        ("1. Scope & Method", main_body.get("scope_method")),
        ("2. Dataset Overview", main_body.get("dataset")),
        ("3. Core Metrics", main_body.get("core_metrics")),
        ("4. Edge Fitness", main_body.get("edge_fitness")),
        ("5. Competitive & Standards", main_body.get("competitive")),
        ("6. Risk Profile", main_body.get("risk_profile")),
        ("7. Ranking & Labelling", main_body.get("ranking")),
        ("8. Decision Cards", main_body.get("candidate_cards")),
        ("9. Conclusion", main_body.get("conclusion")),
    ]:
        lines.append(title)
        if isinstance(payload, dict):
            for key, value in payload.items():
                if value in (None, "", []):
                    continue
                if isinstance(value, list):
                    lines.append(f"  - {key}: {', '.join(map(str, value))}")
                else:
                    lines.append(f"  - {key}: {value}")
        elif isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    text = "; ".join(f"{k}={v}" for k, v in item.items() if v not in (None, ""))
                else:
                    text = str(item)
                lines.append(f"  - {text}")
        elif payload:
            lines.append(f"  - {payload}")
        lines.append("")

    lines.append("REFERENCE")
    for idx, ref in enumerate(report_payload.get("references", []), start=1):
        lines.append(f"[R{idx}] {ref.get('source')} - {ref.get('url')}")
    lines.append("")

    lines.append("APPENDIX")
    appendix = report_payload.get("appendix", {})
    for key, value in appendix.items():
        if isinstance(value, dict):
            lines.append(f"- {key}: " + ", ".join(f"{k}={v}" for k, v in value.items()))
        else:
            lines.append(f"- {key}: {value}")
    lines.append("")

    lines.append("Evidence Summary")
    evidence = report_payload.get("evidence", {})
    for category, payload in evidence.items():
        badge = _format_badge(badges.get(category, "Local RAG"))
        lines.append(f"[{category.upper()}] {badge}")
        if category == "trl":
            lines.append(f"  TRL level: {payload.get('level', 'N/A')}")
        if category == "claims":
            avg_tokens = payload.get("avg_len_tokens") or 0.0
            lines.append(f"  Independent claims: {payload.get('num_independent', 'N/A')}, Avg tokens: {avg_tokens:.1f}")
        for idx, snippet in enumerate(payload.get("snippets", [])[:max_snippets], start=1):
            lines.append(f"  {idx}. {snippet.get('text', '')}")
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
        except Exception as exc:  # pragma: no cover - fallback on rendering failure
            print(f"[report] PDF rendering failed: {exc}")
            pdf_path.unlink(missing_ok=True)

    text_path = reports_dir / f"report_{safe_ts}.txt"
    _render_text(report_payload, text_path)
    return str(text_path)


__all__ = ["compile_report_pdf"]
