-- GM_BENCH: samples scheduler drift + live group/unit counts every N seconds.
-- Logs to dcs.log via env.info(). Parsed by afterburner bench analysis.
--
-- Log line format:
--   GM_BENCH drift=0.041s groups=47 units=312 elapsed=123.4

local INTERVAL = 5 -- seconds between samples

env.info("GM_BENCH started")

local _expected = timer.getTime() + INTERVAL

local function _count()
	local groups, units = 0, 0
	for _, side in ipairs({ coalition.side.RED, coalition.side.BLUE, coalition.side.NEUTRAL }) do
		for _, g in ipairs(coalition.getGroups(side) or {}) do
			if g and g:isExist() and g:getSize() > 0 then
				groups = groups + 1
				units = units + g:getSize()
			end
		end
	end
	return groups, units
end

local function _tick(_, t)
	local drift = t - _expected
	local ok, groups, units = pcall(_count)
	if ok then
		env.info(string.format("GM_BENCH drift=%.3fs groups=%d units=%d elapsed=%.1f", drift, groups, units, t))
	else
		env.error("GM_BENCH count failed: " .. tostring(groups))
	end
	_expected = _expected + INTERVAL
	return _expected
end

timer.scheduleFunction(_tick, nil, _expected)
