-- luacheck configuration for DCS World Lua scripts
-- DCS uses Lua 5.1

std = "lua51"

-- Treat warnings as errors for these codes:
-- W111: setting undefined global
-- W112: mutating undefined global
-- W113: accessing undefined global
-- (luacheck default is to warn; set to error for CI blocking)

-- DCS scripting environment globals
-- These are injected by the DCS engine and must not be flagged as undefined
globals = {
    -- Core DCS singletons
    "world",
    "coalition",
    "timer",
    "net",
    "trigger",
    "env",
    "land",
    "atmosphere",
    "radio",

    -- DCS object classes
    "Unit",
    "Weapon",
    "StaticObject",
    "Airbase",
    "Group",
    "Object",
    "Controller",
    "Country",

    -- DCS enumerations
    "AI",

    -- Common framework globals (set when frameworks are loaded)
    -- MOOSE
    "BASE",
    "MOOSE",
    "SPAWN",
    "SET_GROUP",
    "SET_UNIT",
    "SCHEDULER",
    "ZONE",
    "ZONE_RADIUS",
    "ZONE_POLYGON",
    "ZONE_GROUP",
    "ZONE_UNIT",
    "MESSAGE",
    "MENU_COALITION",
    "MENU_COALITION_COMMAND",
    "MENU_GROUP",
    "MENU_GROUP_COMMAND",
    "MENU_MISSION",
    "MENU_MISSION_COMMAND",
    "ATIS",
    "AIRBASEPOLICE_BASE",
    "FLIGHTGROUP",
    "GROUNDGROUP",
    "NAVYGROUP",
    "ARMYGROUP",
    "INTEL",
    "INTEL_DLINK",
    "DESIGNATE",
    "DETECTION_BASE",
    "DETECTION_AREAS",
    "DETECTION_TYPES",
    "DETECTION_UNITS",
    "AUFTRAG",
    "OPSTRANSPORT",
    "OPSGROUP",
    "BRIGADE",
    "BATTALION",
    "ARMYGROUP",
    "CHIEF",
    "COMMANDER",
    "LEGION",
    "AIRWING",
    "FLIGHT",
    "TANKER",
    "AWACS",
    "RECCE",
    "RESCUEHELO",
    "SUPPRESSION",
    "COORDINATE",
    "POINT_VEC2",
    "POINT_VEC3",
    "UTILS",
    "CSAR",
    "CTLD",
    "CTLD_CARGO",

    -- MIST
    "mist",

    -- CTLD standalone
    "ctld",

    -- Skynet IADS
    "SkynetIADS",
    "SkynetIADSRadarElement",
    "SkynetIADSSamSite",
    "SkynetIADSAirbase",
    "SkynetIADSEarlyWarningRadar",

    -- CSAR standalone
    "csar",

    -- Common mission script patterns
    "MarkupObject",
    "SceneryObject",
}

-- Files and directories to exclude
exclude_files = {
    -- Third-party framework sources — lint these separately if at all
    "Moose/**",
    "MOOSE/**",
    "Mist/**",
    "MIST/**",
    "mist/**",
    "Scripts/Moose/**",
    "Scripts/MOOSE/**",
    "Scripts/Mist/**",
    "Scripts/mist/**",
    "l10n/**",
}

-- Ignore line length warnings — DCS scripts often have long table literals
ignore = {
    "631", -- line too long
}

-- Max line length (relaxed for DCS mission tables)
max_line_length = false

-- Allow unused arguments (common in DCS event handler patterns)
-- e.g. function handler:onEvent(event) ... end where handler is unused
unused_args = false
