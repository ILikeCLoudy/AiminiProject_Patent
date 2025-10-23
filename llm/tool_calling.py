"""LLM Tool Calling for TRL and Claims evaluation with transparency."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# Tool definitions
TRL_EVALUATION_TOOL = {
    "type": "function",
    "function": {
        "name": "evaluate_trl_level",
        "description": "Evaluate Technology Readiness Level (TRL) based on evidence snippets. TRL ranges from 1-9, where 1 is basic research and 9 is fully deployed in operational environment.",
        "parameters": {
            "type": "object",
            "properties": {
                "trl_level": {
                    "type": "number",
                    "description": "The estimated TRL level (1-9, can be fractional like 6.5)"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score (0.0-1.0)"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Explanation of why this TRL level was assigned, citing specific evidence"
                },
                "key_indicators": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key phrases or indicators from the evidence that support this TRL level"
                }
            },
            "required": ["trl_level", "confidence", "reasoning", "key_indicators"]
        }
    }
}

CLAIM_EVALUATION_TOOL = {
    "type": "function",
    "function": {
        "name": "evaluate_claim_quality",
        "description": "Evaluate patent claim quality based on breadth, clarity, and strategic value.",
        "parameters": {
            "type": "object",
            "properties": {
                "quality_score": {
                    "type": "number",
                    "description": "Overall claim quality score (0-100)"
                },
                "breadth_assessment": {
                    "type": "string",
                    "enum": ["too_narrow", "optimal", "too_broad", "unclear"],
                    "description": "Assessment of claim scope"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score (0.0-1.0)"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Explanation of the quality assessment"
                },
                "strengths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Identified strengths of the claims"
                },
                "weaknesses": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Identified weaknesses or areas for improvement"
                }
            },
            "required": ["quality_score", "breadth_assessment", "confidence", "reasoning"]
        }
    }
}


def evaluate_trl_with_llm(
    snippets: List[Dict[str, Any]],
    keyword_based_score: Optional[float],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Use LLM Tool Calling to evaluate TRL level with reasoning.

    Args:
        snippets: Evidence snippets containing text
        keyword_based_score: Fallback score from keyword matching
        config: LLM configuration

    Returns:
        Dictionary with trl_level, confidence, reasoning, source, and fallback_score
    """
    if OpenAI is None or not os.getenv("OPENAI_API_KEY"):
        return {
            "trl_level": keyword_based_score,
            "confidence": 0.7,
            "reasoning": "Keyword-based estimation (LLM unavailable)",
            "source": "keyword_matching",
            "key_indicators": [],
            "fallback_score": keyword_based_score
        }

    if not snippets:
        return {
            "trl_level": keyword_based_score or 4.0,
            "confidence": 0.3,
            "reasoning": "No evidence available for TRL assessment",
            "source": "default",
            "key_indicators": [],
            "fallback_score": keyword_based_score
        }

    # Prepare evidence text
    evidence_text = "\n\n".join([
        f"Evidence {i+1}: {s.get('text', '')}"
        for i, s in enumerate(snippets[:5])  # Limit to 5 snippets
    ])

    prompt = f"""You are a patent technology readiness expert. Analyze the following evidence snippets and evaluate the Technology Readiness Level (TRL).

TRL Scale Reference:
- TRL 1-3: Basic research, concept formulation
- TRL 4-5: Lab validation, prototype in relevant environment
- TRL 6-7: Pilot testing, field demonstrations
- TRL 8-9: Operational deployment, fully commercialized

Evidence Snippets:
{evidence_text}

Keyword-based estimate: {keyword_based_score if keyword_based_score is not None else 'N/A'}

Please evaluate the TRL level using the evaluate_trl_level function. Consider:
1. Deployment status (lab, pilot, production)
2. Environment (simulated vs. operational)
3. Maturity indicators (testing, validation, commercial use)
4. Risk level (experimental vs. proven)
"""

    try:
        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            timeout=config.get("llm", {}).get("timeout_s", 30)
        )

        response = client.chat.completions.create(
            model=config.get("llm", {}).get("model", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            tools=[TRL_EVALUATION_TOOL],
            tool_choice={"type": "function", "function": {"name": "evaluate_trl_level"}},
            temperature=0.2,  # Low temperature for consistency
            max_tokens=500
        )

        # Extract tool call
        message = response.choices[0].message
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            args = json.loads(tool_call.function.arguments)

            return {
                "trl_level": float(args.get("trl_level", keyword_based_score or 4.0)),
                "confidence": float(args.get("confidence", 0.8)),
                "reasoning": args.get("reasoning", ""),
                "key_indicators": args.get("key_indicators", []),
                "source": "llm_tool_calling",
                "fallback_score": keyword_based_score,
                "model": config.get("llm", {}).get("model", "gpt-4o-mini")
            }

    except Exception as e:
        # Fallback to keyword-based on error
        return {
            "trl_level": keyword_based_score or 4.0,
            "confidence": 0.6,
            "reasoning": f"LLM evaluation failed ({str(e)[:100]}), using keyword-based fallback",
            "source": "keyword_matching_fallback",
            "key_indicators": [],
            "fallback_score": keyword_based_score,
            "error": str(e)
        }

    # Fallback if no tool call
    return {
        "trl_level": keyword_based_score or 4.0,
        "confidence": 0.7,
        "reasoning": "Keyword-based estimation (no tool call returned)",
        "source": "keyword_matching",
        "key_indicators": [],
        "fallback_score": keyword_based_score
    }


def evaluate_claims_with_llm(
    num_independent: int,
    avg_len_tokens: float,
    snippets: List[Dict[str, Any]],
    baseline_score: Optional[float],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Use LLM Tool Calling to evaluate claim quality with reasoning.

    Args:
        num_independent: Number of independent claims
        avg_len_tokens: Average claim length in tokens
        snippets: Claim text snippets
        baseline_score: Fallback score from U-shaped formula
        config: LLM configuration

    Returns:
        Dictionary with quality_score, confidence, reasoning, source
    """
    if OpenAI is None or not os.getenv("OPENAI_API_KEY"):
        return {
            "quality_score": baseline_score,
            "breadth_assessment": "optimal" if baseline_score and baseline_score >= 80 else "unclear",
            "confidence": 0.7,
            "reasoning": "Formula-based calculation (LLM unavailable)",
            "source": "formula",
            "strengths": [],
            "weaknesses": [],
            "fallback_score": baseline_score
        }

    if num_independent <= 0:
        return {
            "quality_score": baseline_score or 50.0,
            "breadth_assessment": "unclear",
            "confidence": 0.3,
            "reasoning": "No independent claims found for evaluation",
            "source": "default",
            "strengths": [],
            "weaknesses": ["No independent claims detected"],
            "fallback_score": baseline_score
        }

    # Prepare claim context
    claims_text = "\n\n".join([
        f"Claim snippet {i+1}: {s.get('text', '')[:500]}"
        for i, s in enumerate(snippets[:3])
    ]) if snippets else "No claim text available"

    prompt = f"""You are a patent attorney evaluating claim quality. Analyze these patent claims:

Claim Statistics:
- Number of independent claims: {num_independent}
- Average claim length: {avg_len_tokens:.1f} tokens

Claim Text:
{claims_text}

Baseline formula score: {baseline_score if baseline_score is not None else 'N/A'}

Evaluate claim quality using the evaluate_claim_quality function. Consider:
1. Breadth: Too narrow (limits protection), optimal (balanced), or too broad (weak enforceability)
2. Clarity: Are claims clear and well-defined?
3. Strategic value: Do claims cover key innovations?
4. Claim count: {num_independent} independent claims - appropriate for technology?
5. Length: {avg_len_tokens:.0f} tokens average - concise or verbose?
"""

    try:
        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            timeout=config.get("llm", {}).get("timeout_s", 30)
        )

        response = client.chat.completions.create(
            model=config.get("llm", {}).get("model", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            tools=[CLAIM_EVALUATION_TOOL],
            tool_choice={"type": "function", "function": {"name": "evaluate_claim_quality"}},
            temperature=0.2,
            max_tokens=600
        )

        message = response.choices[0].message
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            args = json.loads(tool_call.function.arguments)

            return {
                "quality_score": float(args.get("quality_score", baseline_score or 50.0)),
                "breadth_assessment": args.get("breadth_assessment", "unclear"),
                "confidence": float(args.get("confidence", 0.8)),
                "reasoning": args.get("reasoning", ""),
                "strengths": args.get("strengths", []),
                "weaknesses": args.get("weaknesses", []),
                "source": "llm_tool_calling",
                "fallback_score": baseline_score,
                "model": config.get("llm", {}).get("model", "gpt-4o-mini")
            }

    except Exception as e:
        return {
            "quality_score": baseline_score or 50.0,
            "breadth_assessment": "optimal" if baseline_score and baseline_score >= 80 else "unclear",
            "confidence": 0.6,
            "reasoning": f"LLM evaluation failed ({str(e)[:100]}), using formula-based fallback",
            "source": "formula_fallback",
            "strengths": [],
            "weaknesses": [],
            "fallback_score": baseline_score,
            "error": str(e)
        }

    return {
        "quality_score": baseline_score or 50.0,
        "breadth_assessment": "optimal" if baseline_score and baseline_score >= 80 else "unclear",
        "confidence": 0.7,
        "reasoning": "Formula-based calculation (no tool call returned)",
        "source": "formula",
        "strengths": [],
        "weaknesses": [],
        "fallback_score": baseline_score
    }


__all__ = ["evaluate_trl_with_llm", "evaluate_claims_with_llm"]
