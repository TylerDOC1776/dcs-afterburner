"""Rule base class, registry, and runner."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import ClassVar

from afterburner.models.findings import ReportFinding
from afterburner.models.mission import Mission

_log = logging.getLogger(__name__)

_registry: list[type[Rule]] = []


def register(cls: type[Rule]) -> type[Rule]:
    _registry.append(cls)
    return cls


def run_all(mission: Mission) -> list[ReportFinding]:
    findings: list[ReportFinding] = []
    for rule_cls in _registry:
        try:
            findings.extend(rule_cls().check(mission))
        except Exception:
            _log.exception("Rule %s raised an unhandled exception", rule_cls.rule_id)
    return findings


class Rule(ABC):
    rule_id: ClassVar[str]

    @abstractmethod
    def check(self, mission: Mission) -> list[ReportFinding]: ...
