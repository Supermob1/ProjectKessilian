NDefines.NGame.START_DATE = "976.1.1.12"
NDefines.NGame.END_DATE = "1100.1.1.1"
NDefines.NBuildings.INFRASTRUCTURE_RESOURCE_BONUS = 0.0
NDefines.NNavy.NAVAL_RANGE_TO_INGAME_DISTANCE = 1
NDefines.NMilitary.CORPS_COMMANDER_DIVISIONS_CAP = 12
NDefines.NMilitary.FIELD_MARSHAL_DIVISIONS_CAP = 16
NDefines.NMilitary.FIELD_MARSHAL_ARMIES_CAP = 5
NDefines.NTrade.NAVAL_ROUTE_ACCESS_AVOID_COST_MULT = 1000
NDefines.NDiplomacy.BASE_CONDITIONAL_PEACE_MONTHS = 1000
NDefines.NCountry.DAYS_OF_WAR_BEFORE_SURRENDER = 10000
NDefines.NFocus.FOCUS_POINT_DAYS = 5
NDefines.NFocus.MAX_SAVED_FOCUS_PROGRESS = 1
NDefines.NGraphics.MAX_NUMBER_OF_TEXTURES = 25000
NDefines.NInterface.SLOW_INTERFACE_THRESHOLD = 25000
-- HOD early war: volunteers are the main way to help (planets are small and ~200 units apart)
NDefines.NDiplomacy.VOLUNTEERS_PER_TARGET_PROVINCE = 3
NDefines.NDiplomacy.VOLUNTEERS_PER_COUNTRY_ARMY = 0.3
NDefines.NDiplomacy.VOLUNTEERS_DIVISIONS_REQUIRED = 3
NDefines.NDiplomacy.TENSION_VOLUNTEER_FORCE_DIVISION = 0.05
NDefines.NAI.MAX_VOLUNTEER_ARMY_FRACTION = 0.3
NDefines.NAI.SEND_VOLUNTEER_EVAL_BASE_DISTANCE = 2500.0

-- HOD: international market switched off (see on_actions/HOD_no_market_on_actions.txt)
NDefines.NMarket.REQUEST_AUTOMATION_AUTO_ACCEPT_MARKET_ACCESS_DEFAULT = false
NDefines.NMarket.REQUEST_AUTOMATION_AUTO_SEND_MARKET_ACCESS_DEFAULT = false
NDefines.NMarket.REQUEST_AUTOMATION_AUTO_ACCEPT_PURCHASE_DEFAULT = false
NDefines.NAI.EQUIPMENT_MARKET_UPDATE_FREQUENCY_DAYS = 100000

-- HOD 2026-11-10 fast fleets (Clone Wars: big fleets built fast, big battles often; see plans & scripts/sw_tree/naval_tree.py)
NDefines.NProduction.DEFAULT_MAX_NAV_FACTORIES_PER_LINE = 15	-- vanilla 10
NDefines.NProduction.CAPITAL_SHIP_MAX_NAV_FACTORIES_PER_LINE = 15	-- vanilla 5: a shipyard world finishes a Star Destroyer in ~2 months
NDefines.NBuildings.NAVALBASE_REPAIR_MULT = 0.15	-- vanilla 0.05: damaged fleets fight again within weeks
NDefines.NNavy.COMBAT_BASE_HIT_CHANCE = 0.14	-- vanilla 0.1: short, bloody battles
NDefines.NNavy.COMBAT_MIN_DURATION = 12	-- vanilla 8: a losing fleet loses ships before it can retreat
NDefines.NNavy.BASE_SPOTTING = 3	-- vanilla 1: fleets on the same hyperlane find each other fast
NDefines.NNavy.HIGHER_SHIP_RATIO_POSITIONING_PENALTY_FACTOR = 0.1	-- vanilla 0.25: big fleets are normal
NDefines.NNavy.MAX_POSITIONING_PENALTY_FROM_HIGHER_SHIP_RATIO = 0.3	-- vanilla 0.75
