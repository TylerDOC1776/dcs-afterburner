"""Inject gm_bench.lua into a .miz as a mission-start DO SCRIPT FILE trigger."""

from __future__ import annotations

import shutil
from pathlib import Path

from afterburner.parsers import lua_table
from afterburner.utils.miz import extract, repack

_BENCH_LUA = Path(__file__).parent / "gm_bench.lua"
_TRIGGER_NAME = "GM_BENCH"
_RESOURCE_NAME = "gm_bench.lua"


def inject(miz_path: Path, output_path: Path) -> None:
    """Produce output_path as a copy of miz_path with gm_bench baked in.

    Adds a ONCE trigger that runs gm_bench.lua via a_do_script_file.

    Raises FileExistsError  if output_path already exists.
    Raises RuntimeError     if a GM_BENCH trigger is already present.
    """
    if output_path.exists():
        raise FileExistsError(f"Output already exists: {output_path}")

    work_dir = extract(miz_path)
    try:
        resource_key = _write_resource(work_dir)
        action = f'a_do_script_file(getValueResourceByKey("{resource_key}"))'
        mission_file = work_dir / "mission"
        raw = lua_table.loads(mission_file.read_text(encoding="utf-8"))
        _add_trigger(raw, action, resource_key)
        mission_file.write_text(
            "mission =\n" + _lua_dumps(raw) + "\n", encoding="utf-8"
        )
        repack(work_dir, output_path, original_miz=miz_path)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _write_resource(work_dir: Path) -> str:
    l10n_dir = work_dir / "l10n" / "DEFAULT"
    l10n_dir.mkdir(parents=True, exist_ok=True)
    (l10n_dir / _RESOURCE_NAME).write_text(
        _BENCH_LUA.read_text(encoding="utf-8"), encoding="utf-8"
    )

    map_resource = l10n_dir / "mapResource"
    if map_resource.exists():
        try:
            raw = lua_table.loads(map_resource.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raw = {}
        except Exception:
            raw = {}
    else:
        raw = {}
    resource_key = _resource_key_for(raw)
    raw[resource_key] = _RESOURCE_NAME
    map_resource.write_text(
        "mapResource =\n" + _lua_dumps(raw) + "\n", encoding="utf-8"
    )
    return resource_key


def _resource_key_for(map_resource: dict) -> str:
    for key, value in map_resource.items():
        if value == _RESOURCE_NAME:
            return str(key)

    # The Mission Editor uses ResKey_Action_* for DO SCRIPT FILE resources.
    # In the Vietguam reference mission it reused the free 235 slot; prefer
    # that if available, otherwise append after the highest action resource.
    if "ResKey_Action_235" not in map_resource:
        return "ResKey_Action_235"

    nums = []
    for key in map_resource:
        if isinstance(key, str) and key.startswith("ResKey_Action_"):
            try:
                nums.append(int(key.rsplit("_", 1)[1]))
            except ValueError:
                pass
    return f"ResKey_Action_{(max(nums) if nums else 0) + 1}"


def _add_trigger(raw: dict, action: str, resource_key: str) -> None:
    trig = raw.setdefault("trig", {})

    for key in ("conditions", "actions", "flag"):
        if key not in trig or not isinstance(trig[key], list):
            trig[key] = _to_lua_array(trig.get(key))

    if _already_injected(raw, resource_key):
        raise RuntimeError("GM_BENCH trigger is already present in this mission")

    trigger_index = len(trig["conditions"]) + 1
    trig["conditions"].append("return(c_time_after(1))")
    trig["actions"].append(f"{action}; mission.trig.func[{trigger_index}]=nil;")
    trig["flag"].append(True)

    func = trig.get("func")
    if not isinstance(func, dict):
        func = _func_dict(func)
        trig["func"] = func
    func[trigger_index] = (
        f"if mission.trig.conditions[{trigger_index}]() then "
        f"mission.trig.actions[{trigger_index}]() end"
    )
    _add_trigrule(raw, resource_key)


def _add_trigrule(raw: dict, resource_key: str) -> None:
    trigrules = raw.get("trigrules")
    rule = {
        "rules": [
            {
                "predicate": "c_time_after",
                "seconds": 1,
            }
        ],
        "comment": _TRIGGER_NAME,
        "eventlist": "",
        "predicate": "triggerOnce",
        "actions": [
            {
                "predicate": "a_do_script_file",
                "file": resource_key,
            }
        ],
        "colorItem": "0x00ff00ff",
    }

    if isinstance(trigrules, list):
        trigrules.append(rule)
    elif isinstance(trigrules, dict):
        keys = [k for k in trigrules if isinstance(k, int)]
        trigrules[(max(keys) if keys else 0) + 1] = rule
    else:
        raw["trigrules"] = [rule]


def _already_injected(raw: dict, resource_key: str) -> bool:
    trig = raw.get("trig", {})
    trigger_names = trig.get("triggerName", [])
    if isinstance(trigger_names, dict):
        trigger_names = trigger_names.values()
    if isinstance(trigger_names, list) and _TRIGGER_NAME in trigger_names:
        return True

    actions = trig.get("actions", [])
    if isinstance(actions, dict):
        actions = actions.values()
    if any(
        resource_key in str(action) or _RESOURCE_NAME in str(action)
        for action in actions
    ):
        return True

    trigrules = raw.get("trigrules", [])
    if isinstance(trigrules, dict):
        trigrules = trigrules.values()
    if isinstance(trigrules, list):
        for rule in trigrules:
            if not isinstance(rule, dict):
                continue
            if rule.get("comment") == _TRIGGER_NAME:
                return True
            rule_actions = rule.get("actions", [])
            if isinstance(rule_actions, dict):
                rule_actions = rule_actions.values()
            if any(_is_bench_action(action, resource_key) for action in rule_actions):
                return True
    return False


def _is_bench_action(action, resource_key: str) -> bool:
    return isinstance(action, dict) and action.get("file") in {
        resource_key,
        _RESOURCE_NAME,
    }


def _to_lua_array(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value[k] for k in sorted(k for k in value if isinstance(k, int))]
    return []


def _func_dict(value) -> dict[int, str]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {i + 1: v for i, v in enumerate(value)}
    return {}


def _lua_dumps(obj, _depth: int = 0) -> str:
    """Serialize a Python object to a DCS-compatible Lua table literal."""
    pad = "  " * _depth
    inner = "  " * (_depth + 1)

    if obj is None:
        return "nil"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, float):
        return repr(obj)
    if isinstance(obj, str):
        s = (
            obj.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )
        return f'"{s}"'
    if isinstance(obj, list):
        if not obj:
            return "{}"
        lines = [
            f"{inner}[{i + 1}] = {_lua_dumps(v, _depth + 1)},"
            for i, v in enumerate(obj)
        ]
        return "{\n" + "\n".join(lines) + "\n" + pad + "}"
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        lines = []
        for k, v in obj.items():
            key_str = f"[{k}]" if isinstance(k, int) else f'["{k}"]'
            lines.append(f"{inner}{key_str} = {_lua_dumps(v, _depth + 1)},")
        return "{\n" + "\n".join(lines) + "\n" + pad + "}"
    return f'"{obj!r}"'
