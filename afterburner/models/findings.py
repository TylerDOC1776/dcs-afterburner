"""Finding and severity models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ReportFinding:
    rule_id: str
    severity: Severity
    title: str
    detail: str
    fix: str | None = None
    confidence: float = field(default=1.0)
