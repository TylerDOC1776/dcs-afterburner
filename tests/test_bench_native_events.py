from __future__ import annotations

from datetime import datetime

from afterburner.bench.native_events import NativeEvent, parse_native_events


def test_parse_native_events_extracts_dcs_scripting_event_fields():
    text = (
        "2026-04-26 20:49:26.819 INFO    Scripting (Main): "
        "event:type=takeoff,initiatorPilotName=Potato,place=Andersen AFB,"
        "t=37839.558,initiator_unit_type=F-4E-45MC,event_id=81229,\n"
    )

    assert parse_native_events(text) == [
        NativeEvent(
            timestamp=datetime(2026, 4, 26, 20, 49, 26, 819000),
            type="takeoff",
            fields={
                "type": "takeoff",
                "initiatorPilotName": "Potato",
                "place": "Andersen AFB",
                "t": "37839.558",
                "initiator_unit_type": "F-4E-45MC",
                "event_id": "81229",
            },
        )
    ]


def test_parse_native_events_accepts_uppercase_scripting_component():
    text = (
        "2026-04-26 20:58:40.531 INFO    SCRIPTING (Main): "
        "event:type=score,initiatorPilotName=Potato,t=38393.258,amount=10,\n"
    )

    event = parse_native_events(text)[0]

    assert event.type == "score"
    assert event.player == "Potato"
    assert event.elapsed_s == 38393.258


def test_parse_native_events_ignores_non_event_lines():
    text = "2026-04-26 20:00:00.000 INFO    APP (Main): Device plugged\n"

    assert parse_native_events(text) == []


def test_native_event_player_falls_back_to_target_pilot_name():
    text = (
        "2026-04-26 20:43:22.671 INFO    Scripting (Main): "
        "event:type=crash,targetPilotName=Potato,t=37475.402,\n"
    )

    assert parse_native_events(text)[0].player == "Potato"


def test_native_event_invalid_elapsed_returns_none():
    text = (
        "2026-04-26 20:43:22.671 INFO    Scripting (Main): "
        "event:type=crash,initiatorPilotName=Potato,t=nope,\n"
    )

    assert parse_native_events(text)[0].elapsed_s is None
