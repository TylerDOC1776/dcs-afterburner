from __future__ import annotations

import pytest

from afterburner.bench.inject import _add_trigger, _resource_key_for


def test_add_trigger_preserves_sparse_func_table():
    raw = {
        "trig": {
            "conditions": ["return(true)", "return(c_time_after(25))"],
            "actions": ["action1", "action2"],
            "flag": [True, True],
            "func": {
                2: "if mission.trig.conditions[2]() then mission.trig.actions[2]() end"
            },
        },
        "trigrules": [
            {
                "rules": [],
                "comment": "Mission Start",
                "eventlist": "",
                "predicate": "triggerStart",
                "actions": [],
            },
            {
                "rules": [{"predicate": "c_time_after", "seconds": 25}],
                "comment": "EWRS",
                "eventlist": "",
                "predicate": "triggerOnce",
                "actions": [
                    {"predicate": "a_do_script_file", "file": "ResKey_Action_240"}
                ],
            },
        ],
    }

    _add_trigger(
        raw,
        'a_do_script_file(getValueResourceByKey("ResKey_Action_235"))',
        "ResKey_Action_235",
    )

    trig = raw["trig"]
    assert trig["func"][2] == (
        "if mission.trig.conditions[2]() then mission.trig.actions[2]() end"
    )
    assert trig["func"][3] == (
        "if mission.trig.conditions[3]() then mission.trig.actions[3]() end"
    )
    assert trig["conditions"][2] == "return(c_time_after(1))"
    assert trig["actions"][2] == (
        'a_do_script_file(getValueResourceByKey("ResKey_Action_235")); '
        "mission.trig.func[3]=nil;"
    )
    assert raw["trigrules"][2] == {
        "rules": [{"predicate": "c_time_after", "seconds": 1}],
        "comment": "GM_BENCH",
        "eventlist": "",
        "predicate": "triggerOnce",
        "actions": [{"predicate": "a_do_script_file", "file": "ResKey_Action_235"}],
        "colorItem": "0x00ff00ff",
    }


def test_add_trigger_rejects_existing_resource_action():
    raw = {
        "trig": {
            "conditions": ["return(c_time_after(1))"],
            "actions": ['a_do_script_file(getValueResourceByKey("ResKey_Action_235"))'],
            "flag": [True],
        }
    }

    with pytest.raises(RuntimeError, match="GM_BENCH trigger is already present"):
        _add_trigger(
            raw,
            'a_do_script_file(getValueResourceByKey("ResKey_Action_235"))',
            "ResKey_Action_235",
        )


def test_add_trigger_rejects_existing_trigrule_resource_action():
    raw = {
        "trig": {
            "conditions": [],
            "actions": [],
            "flag": [],
        },
        "trigrules": [
            {
                "comment": "GM_BENCH",
                "actions": [
                    {"predicate": "a_do_script_file", "file": "ResKey_Action_235"}
                ],
            }
        ],
    }

    with pytest.raises(RuntimeError, match="GM_BENCH trigger is already present"):
        _add_trigger(
            raw,
            'a_do_script_file(getValueResourceByKey("ResKey_Action_235"))',
            "ResKey_Action_235",
        )


def test_resource_key_for_prefers_mission_editor_key_when_free():
    assert _resource_key_for({"ResKey_Action_234": "x.lua"}) == "ResKey_Action_235"


def test_resource_key_for_reuses_existing_gm_bench_resource():
    assert (
        _resource_key_for({"ResKey_Action_241": "gm_bench.lua"}) == "ResKey_Action_241"
    )


def test_resource_key_for_appends_when_235_is_taken():
    assert (
        _resource_key_for(
            {"ResKey_Action_235": "other.lua", "ResKey_Action_240": "x.lua"}
        )
        == "ResKey_Action_241"
    )
