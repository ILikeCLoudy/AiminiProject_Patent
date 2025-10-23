"""Narrative text formatting for patent assessment reports."""
from __future__ import annotations

from typing import Any, Dict, List


def format_scope_method(data: Dict[str, Any]) -> List[str]:
    """Convert scope & method section to narrative paragraphs."""
    narratives: List[str] = []

    scope = data.get("scope", {})
    method = data.get("method", {})

    # Scope narrative
    if scope:
        keywords = scope.get("keywords", "")
        cpc = scope.get("cpc", "")
        period = scope.get("period", "")
        target = scope.get("target_market", "")

        scope_text = (
            f"This assessment focuses on patents related to {keywords or 'the specified technology'}, "
            f"classified under CPC codes {cpc or 'various categories'}. "
            f"The analysis period spans from {period or 'unspecified dates'}, "
            f"with emphasis on {target or 'general market'} applications."
        )
        narratives.append(scope_text)

    # Method narrative
    if method:
        norm = method.get("normalisation", "")
        weights = method.get("weights", "")
        rules = method.get("label_rule", "")

        method_text = (
            f"Our evaluation methodology applies {norm or 'standard normalization'} to ensure fair comparison across metrics. "
            f"Individual metrics are combined using {weights or 'predefined weights'} to produce a comprehensive score. "
            f"Final recommendations follow {rules or 'established decision rules'} based on overall performance and risk factors."
        )
        narratives.append(method_text)

    return narratives


def format_dataset(data: Dict[str, Any]) -> List[str]:
    """Convert dataset overview to narrative."""
    narratives: List[str] = []

    doc_count = data.get("documents", 0)
    family_size = data.get("family_size", 0)
    quality = data.get("quality", {})

    # Document count narrative
    dataset_text = (
        f"We analyzed {doc_count} patent document(s) in this assessment. "
        f"The patent family consists of {family_size} member(s) across different jurisdictions."
    )
    narratives.append(dataset_text)

    # Quality issues
    if quality:
        missing = quality.get("missing_metrics", [])
        if missing:
            quality_text = (
                f"Data quality note: {len(missing)} metrics ({', '.join(missing[:3])}"
                f"{', ...' if len(missing) > 3 else ''}) could not be retrieved from public sources. "
                f"This may affect the comprehensiveness of our analysis."
            )
            narratives.append(quality_text)

    return narratives


def format_core_metrics(data: Dict[str, Any]) -> List[str]:
    """Convert core metrics to narrative explanations."""
    narratives: List[str] = []

    # Citations
    citations = data.get("citations_total", 0)
    if citations == 0:
        cit_text = (
            "This patent has not yet been cited by other patents. "
            "This could indicate a recent filing, or suggest limited technical influence in the field."
        )
    elif citations < 5:
        cit_text = (
            f"This patent has been cited {citations} time(s) by other patents, "
            "indicating emerging recognition in the technical community."
        )
    else:
        cit_text = (
            f"This patent has received {citations} forward citations, "
            "demonstrating significant technical influence and relevance to subsequent innovations."
        )
    narratives.append(cit_text)

    # Family
    family = data.get("family", 1)
    if family == 1:
        fam_text = (
            "This is a standalone patent with no international family members. "
            "The applicant has not filed equivalent applications in other jurisdictions."
        )
    else:
        fam_text = (
            f"This patent belongs to a family of {family} members across multiple jurisdictions, "
            "indicating the applicant's strategic interest in international protection."
        )
    narratives.append(fam_text)

    # Legal status
    legal = data.get("legal_status", "")
    if legal.lower() == "active":
        legal_text = (
            "The patent is currently active and in force, with maintenance fees paid up to date. "
            "This indicates ongoing commercial value and strategic importance to the patent holder."
        )
    elif legal.lower() in ("expired", "abandoned"):
        legal_text = (
            f"The patent is {legal}, meaning it no longer provides exclusive rights. "
            "This may present freedom-to-operate opportunities for our implementation."
        )
    else:
        legal_text = f"Legal status: {legal or 'Unknown - requires further investigation'}."
    narratives.append(legal_text)

    # TRL score
    trl = data.get("trl_score")
    if trl is not None:
        if trl >= 8:
            trl_text = (
                f"Technology Readiness Level (TRL) analysis scores this patent at {trl:.1f}, "
                "indicating the technology has been deployed in operational environments. "
                "This suggests high maturity and proven real-world viability."
            )
        elif trl >= 6:
            trl_text = (
                f"Technology Readiness Level (TRL) of {trl:.1f} indicates the technology "
                "has been demonstrated in relevant environments through pilot testing. "
                "Further validation may be needed before full-scale deployment."
            )
        else:
            trl_text = (
                f"Technology Readiness Level (TRL) of {trl:.1f} suggests early-stage development. "
                "The technology requires significant additional work before commercial readiness."
            )
        narratives.append(trl_text)

    # Claim score
    claim = data.get("claim_score")
    if claim is not None:
        if claim >= 80:
            claim_text = (
                f"Claim breadth analysis yields a score of {claim:.1f}, "
                "indicating well-structured claims with balanced scope. "
                "The patent provides strong protection without being overly broad or narrow."
            )
        elif claim >= 60:
            claim_text = (
                f"Claim breadth score of {claim:.1f} suggests moderate patent coverage. "
                "The claims may benefit from refinement to optimize protection scope."
            )
        else:
            claim_text = (
                f"Claim breadth score of {claim:.1f} indicates potential limitations in patent scope. "
                "The claims may be too narrow or verbose, limiting enforcement options."
            )
        narratives.append(claim_text)

    return narratives


def format_edge_fitness(data: Dict[str, Any]) -> List[str]:
    """Convert edge fitness metrics to narrative."""
    narratives: List[str] = []

    # Handle nested metrics structure from extract_edge_performance
    if isinstance(data, dict) and not data:
        return [
            "Edge device performance metrics were not available for this patent. "
            "Assessment could not be performed due to lack of experimental data or benchmarks in public sources."
        ]

    # Extract metrics if nested
    metrics = data if not isinstance(data.get("latency_ms"), dict) else {
        k: v.get("value") if isinstance(v, dict) else v
        for k, v in data.items()
    }

    # Check if all values are None
    if all(v is None for v in metrics.values()):
        return [
            "Edge device performance metrics were not available for this patent. "
            "Assessment could not be performed due to lack of experimental data or benchmarks in public sources."
        ]

    # Get thresholds from config (defaults)
    latency_threshold = 50
    power_threshold = 600
    memory_threshold = 256

    # Latency
    latency = metrics.get("latency_ms")
    if latency is not None:
        if latency <= latency_threshold:
            lat_text = (
                f"Inference latency is measured at {latency}ms, which meets the edge deployment "
                f"threshold of {latency_threshold}ms. This indicates real-time processing capability."
            )
        else:
            lat_text = (
                f"Inference latency of {latency}ms exceeds the target threshold ({latency_threshold}ms). "
                "Optimization may be required for latency-critical edge applications."
            )
        narratives.append(lat_text)

    # Power
    power = metrics.get("power_mw")
    if power is not None:
        if power <= power_threshold:
            pow_text = (
                f"Power consumption is {power}mW, meeting the edge device budget of {power_threshold}mW. "
                "This enables battery-powered deployment scenarios."
            )
        else:
            pow_text = (
                f"Power consumption of {power}mW exceeds the budget ({power_threshold}mW). "
                "This may limit applicability to power-constrained devices."
            )
        narratives.append(pow_text)

    # Memory
    memory = metrics.get("memory_mb")
    if memory is not None:
        if memory <= memory_threshold:
            mem_text = (
                f"Memory footprint is {memory}MB, fitting within the {memory_threshold}MB edge device constraint. "
                "The model can run on resource-limited hardware."
            )
        else:
            mem_text = (
                f"Memory requirement of {memory}MB exceeds the {memory_threshold}MB limit. "
                "Model compression techniques may be necessary."
            )
        narratives.append(mem_text)

    # Accuracy delta
    acc_delta = metrics.get("accuracy_delta")
    if acc_delta is not None:
        if acc_delta >= 0:
            acc_text = (
                f"Accuracy compared to baseline shows {acc_delta:+.1f}% change, "
                "indicating no degradation from edge optimization."
            )
        elif acc_delta >= -2:
            acc_text = (
                f"Accuracy shows {acc_delta:+.1f}% change compared to baseline. "
                "This minor degradation is acceptable for edge deployment."
            )
        else:
            acc_text = (
                f"Accuracy degradation of {acc_delta:+.1f}% raises concerns. "
                "Further optimization may be needed to balance accuracy and efficiency."
            )
        narratives.append(acc_text)

    return narratives


def format_competitive(data: Dict[str, Any]) -> List[str]:
    """Convert competitive & standards section to narrative."""
    narratives: List[str] = []

    sep = data.get("sep", "")

    if sep == "declared":
        sep_text = (
            "This patent has been declared as a Standard-Essential Patent (SEP), "
            "meaning it is essential for implementing certain industry standards. "
            "This provides significant strategic value but may carry FRAND licensing obligations."
        )
    elif sep == "not_declared":
        sep_text = (
            "This patent has not been declared as standard-essential. "
            "While this provides greater licensing flexibility, it may have limited standards-based value."
        )
    else:
        sep_text = (
            "Standard-Essential Patent (SEP) status could not be determined. "
            "Further investigation with standards organizations (ETSI, IEEE, etc.) is recommended."
        )
    narratives.append(sep_text)

    return narratives


def format_risk_profile(data: Dict[str, Any]) -> List[str]:
    """Convert risk profile to narrative."""
    narratives: List[str] = []

    gaps = data.get("data_gaps", [])

    if gaps:
        gap_text = (
            f"Risk assessment identified {len(gaps)} missing data points: {', '.join(gaps[:3])}"
            f"{', ...' if len(gaps) > 3 else ''}. "
            "These gaps reduce confidence in certain aspects of the analysis. "
            "Manual verification from additional sources is strongly recommended before making final decisions."
        )
        narratives.append(gap_text)
    else:
        gap_text = "All key metrics were successfully retrieved, providing high confidence in the assessment."
        narratives.append(gap_text)

    return narratives


def format_ranking(data: Dict[str, Any]) -> List[str]:
    """Convert ranking & labelling to narrative."""
    narratives: List[str] = []

    total = data.get("total_score")
    label = data.get("label", "")

    if total is not None:
        rank_text = (
            f"The overall weighted score for this patent is {total:.2f} out of 100, "
            f"resulting in a recommendation label of '{label}'. "
        )

        if label == "A":
            rank_text += (
                "This 'Adopt' label indicates the patent represents a strong opportunity "
                "with favorable technical, market, and legal characteristics. Immediate action is recommended."
            )
        elif label == "P":
            rank_text += (
                "This 'Prototype' label suggests the patent shows promise but requires further validation. "
                "Consider a pilot implementation or deeper technical due diligence before full commitment."
            )
        elif label == "M":
            rank_text += (
                "This 'Monitor' label indicates marginal value at present. "
                "Continue tracking developments but defer investment until conditions improve."
            )
        else:
            rank_text += (
                "The patent does not currently meet our strategic criteria. "
                "Archive for potential future reconsideration if circumstances change."
            )

        narratives.append(rank_text)

    return narratives


def format_conclusion(data: Dict[str, Any]) -> List[str]:
    """Convert conclusion section to narrative."""
    # Conclusion is typically already in narrative form in summary_card
    # This is a fallback for main_body conclusion
    if isinstance(data, dict):
        return [f"{k}: {v}" for k, v in data.items() if v]
    elif isinstance(data, list):
        return data
    return [str(data)] if data else []


def format_candidate_cards(cards: List[Dict[str, Any]]) -> List[str]:
    """Convert decision cards to narrative."""
    narratives: List[str] = []

    for card in cards:
        title = card.get("title", "Unknown")
        decision = card.get("decision", "")
        signals = card.get("signals", [])
        risks = card.get("risks", [])

        card_text = (
            f"Patent {title}: Recommended action is '{decision}'. "
            f"Key positive signals include: {', '.join(signals) if signals else 'none identified'}. "
        )

        if risks:
            risk_items = [r.get("item", "") for r in risks if isinstance(r, dict)]
            card_text += f"Risk factors to consider: {', '.join(risk_items)}."

        narratives.append(card_text)

    return narratives


def format_main_body_section(section_name: str, data: Any) -> List[str]:
    """Main dispatcher for formatting different sections."""
    if not data:
        return [f"No data available for {section_name}."]

    formatters = {
        "scope_method": format_scope_method,
        "dataset": format_dataset,
        "core_metrics": format_core_metrics,
        "edge_fitness": format_edge_fitness,
        "competitive": format_competitive,
        "risk_profile": format_risk_profile,
        "ranking": format_ranking,
        "conclusion": format_conclusion,
        "candidate_cards": format_candidate_cards,
    }

    formatter = formatters.get(section_name)
    if formatter:
        if section_name == "candidate_cards" and isinstance(data, list):
            return formatter(data)
        elif isinstance(data, dict):
            return formatter(data)

    # Fallback: return as-is
    if isinstance(data, dict):
        return [f"{k}: {v}" for k, v in data.items() if v not in (None, "", [])]
    elif isinstance(data, list):
        return [str(item) for item in data]
    return [str(data)]


__all__ = ["format_main_body_section"]
