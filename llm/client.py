"""OpenAI LLM client wrapper for patent analysis."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class LLMClient:
    """Wrapper for OpenAI chat completion API."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 500,
        timeout: int = 30,
    ):
        """
        Initialize LLM client.

        Args:
            model: Model name (default: gpt-4o-mini)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum output tokens
            timeout: Request timeout in seconds
        """
        if OpenAI is None:
            raise ImportError("openai package is required for LLM functionality")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate_summary(
        self,
        patent_text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate Problem-Solution-Evidence summary for a patent.

        Args:
            patent_text: Patent abstract/claims text
            context: Additional context (TRL, citations, etc.)

        Returns:
            3-sentence P-S-E summary
        """
        context = context or {}

        # Build context string
        context_parts = []
        if context.get("trl_level"):
            context_parts.append(f"TRL: {context['trl_level']}")
        if context.get("citations"):
            context_parts.append(f"Citations: {context['citations']}")
        if context.get("family_size"):
            context_parts.append(f"Family size: {context['family_size']}")

        context_str = ", ".join(context_parts) if context_parts else "No additional context"

        prompt = f"""Analyze this patent and generate a concise 3-sentence summary following the Problem-Solution-Evidence (P-S-E) format:

Patent Text:
{patent_text[:2000]}

Context: {context_str}

Generate exactly 3 sentences:
1. Problem: What technical problem does this patent address?
2. Solution: What is the key technical approach or innovation?
3. Evidence: What evidence supports its validity? (cite TRL, citations, or technical details)

Keep each sentence under 50 words. Be specific and technical."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            summary = response.choices[0].message.content.strip()
            return summary

        except Exception as e:
            # Fallback to template-based summary
            return self._fallback_summary(context)

    def extract_from_html(
        self,
        html_snippet: str,
        extraction_task: str,
    ) -> Optional[str]:
        """
        Extract structured data from HTML using LLM.

        Args:
            html_snippet: HTML text to analyze
            extraction_task: Description of what to extract

        Returns:
            Extracted information as string
        """
        prompt = f"""Extract the following information from this HTML snippet:

Task: {extraction_task}

HTML:
{html_snippet[:1500]}

Provide only the extracted value, no explanation. If not found, return "N/A"."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=100,
            )

            result = response.choices[0].message.content.strip()
            return result if result != "N/A" else None

        except Exception:
            return None

    def _fallback_summary(self, context: Dict[str, Any]) -> str:
        """Generate template-based summary as fallback."""
        trl = context.get("trl_level", "N/A")
        citations = context.get("citations", 0)
        family = context.get("family_size", 1)

        problem = "Problem: Address technical challenges in the specified domain with novel approach."
        solution = f"Solution: Implement innovative method with {family} family member(s) across jurisdictions."
        evidence = f"Evidence: TRL estimate {trl}, {citations} forward citations demonstrate validation."

        return f"{problem} {solution} {evidence}"


def get_llm_client(config: Optional[Dict[str, Any]] = None) -> LLMClient:
    """
    Factory function to create LLM client from config.

    Args:
        config: Configuration dictionary

    Returns:
        Configured LLM client
    """
    config = config or {}
    llm_cfg = config.get("llm", {})

    model = llm_cfg.get("model", config.get("planner_llm", "gpt-4o-mini"))
    temperature = llm_cfg.get("temperature", 0.3)
    max_tokens = llm_cfg.get("max_tokens", 500)
    timeout = llm_cfg.get("timeout_s", 30)

    return LLMClient(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


__all__ = ["LLMClient", "get_llm_client"]
