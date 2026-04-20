"""Parse a DCS .miz file into a Mission model."""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from afterburner.models.mission import (
    Category,
    Group,
    Mission,
    MissionSummary,
    Trigger,
    Unit,
    Zone,
)
from afterburner.parsers import lua_table
from afterburner.utils.miz import extract

# Matches getValueDictByKey("DictKey_...") — path stored in l10n dictionary
_DICT_KEY_RE = re.compile(r'getValueDictByKey\("([^"]+)"\)')
# Matches getValueResourceByKey("ResKey_...") — path stored in l10n/DEFAULT/mapResource
_RES_KEY_RE = re.compile(r'getValueResourceByKey\("([^"]+)"\)')
# Matches a bare quoted .lua path: "Scripts/CTLD.lua"
_QUOTED_LUA_RE = re.compile(r'"([^"]+\.lua)"')


def parse(miz_path: str | Path) -> Mission:
    """Extract the .miz, parse the mission table, return a Mission model."""
    miz_path = Path(miz_path)
    work_dir = extract(miz_path)
    try:
        sha256 = _hash_file(miz_path)
        raw = lua_table.loads((work_dir / "mission").read_text(encoding="utf-8"))
        dictionary = _load_dictionary(work_dir)
        resource_map = _load_resource_map(work_dir)
        mission = _build_mission(raw, miz_path.name, sha256, dictionary, resource_map)
        mission.script_loc = _count_script_loc(work_dir, mission.script_files)
        return mission
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _count_script_loc(work_dir: Path, script_files: list[str]) -> dict[str, int]:
    """Return per-file non-blank line counts for all script files in the extracted .miz."""
    search_dirs = [work_dir / "l10n" / "DEFAULT", work_dir]
    result: dict[str, int] = {}
    for name in script_files:
        for d in search_dirs:
            candidate = d / name
            if candidate.exists():
                try:
                    lines = candidate.read_text(
                        encoding="utf-8", errors="replace"
                    ).splitlines()
                    result[name] = sum(1 for ln in lines if ln.strip())
                except OSError:
                    pass
                break
    return result


def _load_dictionary(work_dir: Path) -> dict[str, str]:
    """Load the l10n dictionary for resolving DictKey_* string references."""
    for candidate in (
        work_dir / "l10n" / "DEFAULT" / "dictionary",
        work_dir / "dictionary",
    ):
        if candidate.exists():
            try:
                raw = lua_table.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return {k: str(v) for k, v in raw.items() if isinstance(v, str)}
            except Exception:
                pass
    return {}


def _load_resource_map(work_dir: Path) -> dict[str, str]:
    """Load l10n/DEFAULT/mapResource for resolving ResKey_* file references."""
    candidate = work_dir / "l10n" / "DEFAULT" / "mapResource"
    if candidate.exists():
        try:
            raw = lua_table.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return {k: str(v) for k, v in raw.items() if isinstance(v, str)}
        except Exception:
            pass
    return {}


# ------------------------------------------------------------------
# Internals
# ------------------------------------------------------------------


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return "sha256:" + h.hexdigest()


def _build_mission(
    raw: dict,
    filename: str,
    sha256: str,
    dictionary: dict[str, str] | None = None,
    resource_map: dict[str, str] | None = None,
) -> Mission:
    theatre = str(raw.get("theatre", "unknown"))
    sortie_raw = str(raw.get("sortie", ""))
    # Resolve DictKey_* references from the l10n dictionary
    sortie = (dictionary or {}).get(sortie_raw, sortie_raw)
    # Fall back to filename stem if sortie is empty or unresolved
    if not sortie or sortie.startswith("DictKey_"):
        sortie = Path(filename).stem

    groups: list[Group] = []
    statics: list[Group] = []

    coalition_data = raw.get("coalition", {})
    for side in ("blue", "red", "neutral"):
        side_data = coalition_data.get(side, {})
        countries = side_data.get("country", [])
        if isinstance(countries, dict):
            countries = list(countries.values())
        for country in countries:
            _extract_groups(country, side, groups, statics)

    zones = _extract_zones(raw.get("triggers", {}))
    trig_raw = raw.get("trig", {})
    trigger_count = _count_triggers(trig_raw)
    triggers_detail, script_files = _parse_triggers_detail(
        trig_raw, dictionary or {}, resource_map or {}
    )

    all_units = [u for g in groups for u in g.units]
    active_units = [u for u in all_units if not u.late_activation]
    player_slots = [u for u in all_units if u.is_player_slot]
    active_groups = [g for g in groups if not g.late_activation]

    summary = MissionSummary(
        theatre=theatre,
        total_units=len(all_units),
        active_units=len(active_units),
        late_units=len(all_units) - len(active_units),
        player_slots=len(player_slots),
        total_groups=len(groups),
        active_groups=len(active_groups),
        total_statics=sum(len(g.units) for g in statics),
        trigger_count=trigger_count,
        zone_count=len(zones),
    )

    return Mission(
        name=sortie,
        source_file=filename,
        sha256=sha256,
        theatre=theatre,
        summary=summary,
        groups=groups,
        statics=statics,
        zones=zones,
        triggers_detail=triggers_detail,
        script_files=script_files,
    )


def _extract_groups(
    country: dict, side: str, groups: list[Group], statics: list[Group]
) -> None:
    for category_name in ("plane", "helicopter", "vehicle", "ship", "train"):
        cat_data = country.get(category_name, {})
        group_list = cat_data.get("group", [])
        if isinstance(group_list, dict):
            group_list = list(group_list.values())
        for grp in group_list:
            groups.append(_parse_group(grp, category_name, side))

    static_data = country.get("static", {})
    static_group_list = static_data.get("group", [])
    if isinstance(static_group_list, dict):
        static_group_list = list(static_group_list.values())
    for grp in static_group_list:
        statics.append(_parse_group(grp, "static", side))


def _parse_group(grp: dict, category_name: str, side: str) -> Group:
    late_activation = bool(grp.get("lateActivation", False))

    units_raw = grp.get("units", [])
    if isinstance(units_raw, dict):
        units_raw = list(units_raw.values())

    units = []
    for u in units_raw:
        skill = str(u.get("skill", ""))
        units.append(
            Unit(
                id=int(u.get("unitId", 0)),
                name=str(u.get("name", "")),
                type=str(u.get("type", "")),
                skill=skill,
                late_activation=late_activation,
                x=float(u.get("x", 0)),
                y=float(u.get("y", 0)),
                is_player_slot=skill in ("Client", "Player"),
            )
        )

    try:
        cat = Category(category_name)
    except ValueError:
        cat = Category.VEHICLE

    return Group(
        id=int(grp.get("groupId", 0)),
        name=str(grp.get("name", "")),
        category=cat,
        coalition=side,
        units=units,
        late_activation=late_activation,
        uncontrolled=bool(grp.get("uncontrolled", False)),
    )


def _extract_zones(triggers: dict) -> list[Zone]:
    zones_raw = triggers.get("zones", [])
    if isinstance(zones_raw, dict):
        zones_raw = list(zones_raw.values())
    zones = []
    for z in zones_raw:
        zones.append(
            Zone(
                id=int(z.get("zoneId", 0)),
                name=str(z.get("name", "")),
                radius=float(z.get("radius", 0)),
                x=float(z.get("x", 0)),
                y=float(z.get("y", 0)),
            )
        )
    return zones


def _count_triggers(trig: dict) -> int:
    """Count triggers from the parallel-array trig table."""
    for key in ("conditions", "actions", "flag"):
        val = trig.get(key)
        if isinstance(val, list) and val:
            return len(val)
        if isinstance(val, dict) and val:
            return len(val)
    return 0


def _to_lua_list(val) -> list:
    """Normalise a Lua parallel-array value (list or int-keyed dict) to a list."""
    if isinstance(val, list):
        return val
    if isinstance(val, dict) and val:
        return [val[k] for k in sorted(val.keys())]
    return []


def _parse_triggers_detail(
    trig: dict, dictionary: dict[str, str], resource_map: dict[str, str]
) -> tuple[list[Trigger], list[str]]:
    """Parse the trig parallel-array table into Trigger objects and script file refs.

    Returns (triggers, script_files) where script_files is a sorted list of
    unique .lua filenames detected in DO SCRIPT FILE trigger actions.
    """
    actions = _to_lua_list(trig.get("actions", []))
    logic_types = _to_lua_list(trig.get("logicType", []))
    names = _to_lua_list(trig.get("triggerName", []))

    count = max(len(actions), len(logic_types), len(names), _count_triggers(trig))

    triggers: list[Trigger] = []
    script_files: set[str] = set()

    for i in range(count):
        action_str = str(actions[i]) if i < len(actions) else ""
        logic_type = str(logic_types[i]) if i < len(logic_types) else "ONCE"
        name = str(names[i]) if i < len(names) else f"trigger_{i + 1}"

        # Extract script file references — search the full action string directly.
        # Note: do NOT try to capture the argument to a_do_script_file() with a
        # regex, because the argument often contains nested parens like
        # getValueResourceByKey("ResKey_...") which break [^)]+ capture groups.
        if "a_do_script_file(" in action_str:
            # ResKey → mapResource (modern DCS — scripts embedded in .miz)
            for res_match in _RES_KEY_RE.finditer(action_str):
                filename = resource_map.get(res_match.group(1), "")
                if filename.lower().endswith(".lua"):
                    script_files.add(Path(filename).name)
            # DictKey → l10n dictionary (older DCS)
            for dict_match in _DICT_KEY_RE.finditer(action_str):
                resolved = dictionary.get(dict_match.group(1), "")
                if resolved.lower().endswith(".lua"):
                    script_files.add(Path(resolved).name)
            # Bare quoted path — only if no key-based reference found
            if not _RES_KEY_RE.search(action_str) and not _DICT_KEY_RE.search(
                action_str
            ):
                for path_match in _QUOTED_LUA_RE.finditer(action_str):
                    script_files.add(Path(path_match.group(1)).name)

        triggers.append(Trigger(name=name, logic_type=logic_type))

    return triggers, sorted(script_files)
