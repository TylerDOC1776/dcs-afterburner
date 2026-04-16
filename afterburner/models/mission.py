"""Core data models for a parsed DCS mission."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Category(str, Enum):
    PLANE = "plane"
    HELICOPTER = "helicopter"
    VEHICLE = "vehicle"
    SHIP = "ship"
    STATIC = "static"
    TRAIN = "train"


@dataclass
class Unit:
    id: int
    name: str
    type: str
    skill: str
    late_activation: bool
    x: float
    y: float
    is_player_slot: bool


@dataclass
class Group:
    id: int
    name: str
    category: Category
    coalition: str  # "blue" / "red" / "neutral"
    units: list[Unit]
    late_activation: bool
    uncontrolled: bool


@dataclass
class Zone:
    id: int
    name: str
    radius: float
    x: float
    y: float


@dataclass
class Trigger:
    name: str
    logic_type: str  # "ONCE" | "MORE"


@dataclass
class MissionSummary:
    theatre: str
    total_units: int
    active_units: int
    late_units: int
    player_slots: int
    total_groups: int
    active_groups: int
    total_statics: int
    trigger_count: int
    zone_count: int


@dataclass
class Mission:
    name: str
    source_file: str
    sha256: str
    theatre: str
    summary: MissionSummary
    groups: list[Group] = field(default_factory=list)
    statics: list[Group] = field(default_factory=list)
    zones: list[Zone] = field(default_factory=list)
    triggers_detail: list[Trigger] = field(default_factory=list)
    script_files: list[str] = field(default_factory=list)
