"""Data models for scoring outputs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PatentMeta:
    """Metadata about a patent used for scoring."""

    doc_id: str
    title: str
    publication_date: str
    cpc: List[str]
    legal_status: Optional[str] = None
    renewal_years: Optional[int] = None
    family_size: Optional[int] = None
    countries: Optional[List[str]] = None
    forward_citations_5y: Optional[int] = None


@dataclass
class EdgeSignals:
    """Structured edge-related signals attached to a patent."""

    std_mention: bool = False
    sep_declared: Optional[bool] = None
    fto_warning: bool = False


@dataclass
class CoreScores:
    """Container for the weighted scoring components."""

    trl_score: Optional[float] = None
    claim_breadth_score: Optional[float] = None
    legal_status_score: Optional[float] = None
    family_size_pct: Optional[float] = None
    foreign_oriented_score: Optional[float] = None
    renewal_score: Optional[float] = None
    std_signal_score: Optional[float] = None
    fto_penalty: Optional[float] = None


@dataclass
class Decision:
    """Final decision and label assignment."""

    total: float
    label: str
    flags: List[str] = field(default_factory=list)
