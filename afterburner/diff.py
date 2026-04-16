"""Compare two parsed Mission objects and render the diff."""

from __future__ import annotations

from dataclasses import dataclass

from afterburner.models.mission import Mission


@dataclass
class SummaryDelta:
    field: str
    label: str
    old: int | str
    new: int | str

    @property
    def delta(self) -> int | None:
        if isinstance(self.old, int) and isinstance(self.new, int):
            return self.new - self.old
        return None


@dataclass
class MissionDiff:
    old_file: str
    new_file: str
    theatre_changed: bool
    old_theatre: str
    new_theatre: str
    summary_deltas: list[SummaryDelta]
    groups_added: list[str]
    groups_removed: list[str]
    zones_added: list[str]
    zones_removed: list[str]
    scripts_added: list[str]
    scripts_removed: list[str]

    @property
    def is_identical(self) -> bool:
        return (
            not self.theatre_changed
            and not self.summary_deltas
            and not self.groups_added
            and not self.groups_removed
            and not self.zones_added
            and not self.zones_removed
            and not self.scripts_added
            and not self.scripts_removed
        )


_SUMMARY_FIELDS: list[tuple[str, str]] = [
    ("total_units", "Total units"),
    ("active_units", "Active units"),
    ("late_units", "Late-activation units"),
    ("player_slots", "Player slots"),
    ("total_groups", "Total groups"),
    ("active_groups", "Active groups"),
    ("total_statics", "Static objects"),
    ("trigger_count", "Triggers"),
    ("zone_count", "Trigger zones"),
]


def compute(old: Mission, new: Mission) -> MissionDiff:
    """Return a MissionDiff describing what changed between two missions."""
    theatre_changed = old.theatre != new.theatre

    deltas: list[SummaryDelta] = []
    for field, label in _SUMMARY_FIELDS:
        old_val = getattr(old.summary, field)
        new_val = getattr(new.summary, field)
        if old_val != new_val:
            deltas.append(
                SummaryDelta(field=field, label=label, old=old_val, new=new_val)
            )

    old_group_names = {g.name for g in old.groups}
    new_group_names = {g.name for g in new.groups}
    groups_added = sorted(new_group_names - old_group_names)
    groups_removed = sorted(old_group_names - new_group_names)

    old_zone_names = {z.name for z in old.zones}
    new_zone_names = {z.name for z in new.zones}
    zones_added = sorted(new_zone_names - old_zone_names)
    zones_removed = sorted(old_zone_names - new_zone_names)

    old_scripts = set(old.script_files)
    new_scripts = set(new.script_files)
    scripts_added = sorted(new_scripts - old_scripts)
    scripts_removed = sorted(old_scripts - new_scripts)

    return MissionDiff(
        old_file=old.source_file,
        new_file=new.source_file,
        theatre_changed=theatre_changed,
        old_theatre=old.theatre,
        new_theatre=new.theatre,
        summary_deltas=deltas,
        groups_added=groups_added,
        groups_removed=groups_removed,
        zones_added=zones_added,
        zones_removed=zones_removed,
        scripts_added=scripts_added,
        scripts_removed=scripts_removed,
    )


def print_diff(diff: MissionDiff) -> None:
    """Render a MissionDiff to the terminal using Rich."""
    from rich.console import Console

    con = Console()
    con.print()
    con.print(
        f"[bold cyan]DCS Afterburner — Diff[/bold cyan]"
        f"  [dim]{diff.old_file}[/dim] → [dim]{diff.new_file}[/dim]"
    )
    con.print()

    if diff.is_identical:
        con.print("[green]No changes detected.[/green]")
        con.print()
        return

    # Theatre change
    if diff.theatre_changed:
        con.print(
            f"  [bold]Theatre[/bold]  "
            f"[red]{diff.old_theatre}[/red] → [green]{diff.new_theatre}[/green]"
        )
        con.print()

    # Summary deltas
    if diff.summary_deltas:
        con.print("[bold]Summary[/bold]")
        for d in diff.summary_deltas:
            delta = d.delta
            if delta is not None:
                sign = "+" if delta > 0 else ""
                color = "green" if delta < 0 else "yellow"
                con.print(
                    f"  {d.label:<26} {d.old} → {d.new}"
                    f"  [{color}]({sign}{delta})[/{color}]"
                )
            else:
                con.print(f"  {d.label:<26} {d.old} → {d.new}")
        con.print()

    # Groups
    if diff.groups_added or diff.groups_removed:
        added = len(diff.groups_added)
        removed = len(diff.groups_removed)
        con.print(
            f"[bold]Groups[/bold]"
            f"  [green]+{added} added[/green]"
            f"  [red]-{removed} removed[/red]"
        )
        for name in diff.groups_added:
            con.print(f"  [green]+[/green] {name}")
        for name in diff.groups_removed:
            con.print(f"  [red]-[/red] {name}")
        con.print()

    # Zones
    if diff.zones_added or diff.zones_removed:
        added = len(diff.zones_added)
        removed = len(diff.zones_removed)
        con.print(
            f"[bold]Zones[/bold]"
            f"  [green]+{added} added[/green]"
            f"  [red]-{removed} removed[/red]"
        )
        for name in diff.zones_added:
            con.print(f"  [green]+[/green] {name}")
        for name in diff.zones_removed:
            con.print(f"  [red]-[/red] {name}")
        con.print()

    # Scripts
    if diff.scripts_added or diff.scripts_removed:
        added = len(diff.scripts_added)
        removed = len(diff.scripts_removed)
        con.print(
            f"[bold]Scripts[/bold]"
            f"  [green]+{added} added[/green]"
            f"  [red]-{removed} removed[/red]"
        )
        for name in diff.scripts_added:
            con.print(f"  [green]+[/green] {name}")
        for name in diff.scripts_removed:
            con.print(f"  [red]-[/red] {name}")
        con.print()


def to_json(diff: MissionDiff) -> dict:
    """Serialize a MissionDiff to a JSON-serializable dict."""
    return {
        "old_file": diff.old_file,
        "new_file": diff.new_file,
        "theatre_changed": diff.theatre_changed,
        "old_theatre": diff.old_theatre,
        "new_theatre": diff.new_theatre,
        "summary_deltas": [
            {
                "field": d.field,
                "label": d.label,
                "old": d.old,
                "new": d.new,
                "delta": d.delta,
            }
            for d in diff.summary_deltas
        ],
        "groups_added": diff.groups_added,
        "groups_removed": diff.groups_removed,
        "zones_added": diff.zones_added,
        "zones_removed": diff.zones_removed,
        "scripts_added": diff.scripts_added,
        "scripts_removed": diff.scripts_removed,
        "is_identical": diff.is_identical,
    }
