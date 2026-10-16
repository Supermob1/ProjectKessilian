NDefines_Graphics.NGraphics.GRADIENT_BORDERS_THICKNESS_STATE = 11.0 --11
NDefines_Graphics.NGraphics.STATE_BORDER_FADE_NEAR = 200
NDefines_Graphics.NGraphics.STATE_BORDER_FADE_FAR = 300
NDefines_Graphics.NGraphics.GRADIENT_BORDERS_COUNTRY_CENTER_THICKNESS = 0.1
NDefines_Graphics.NGraphics.GRADIENT_BORDERS_THICKNESS_COUNTRY_LOW = 0.0
NDefines_Graphics.NGraphics.GRADIENT_BORDERS_THICKNESS_COUNTRY_HIGH = 20.0
NDefines_Graphics.NMapMode.SELECTED_COUNTRY_HIGHLIGHT_THICKNESS_MULT = 0.6
NDefines_Graphics.NGraphics.COUNTRY_COLOR_SATURATION_MODIFIER = 0.5
NDefines_Graphics.NGraphics.COUNTRY_COLOR_BRIGHTNESS_MODIFIER = 0.65
NDefines_Graphics.NGraphics.GRADIENT_BORDERS_THICKNESS_SUPPLY_AREA_A = 150.0
NDefines_Graphics.NGraphics.GRADIENT_BORDERS_THICKNESS_SUPPLY_AREA_B = 150.0
NDefines_Graphics.NGraphics.GRADIENT_BORDERS_CAMERA_DISTANCE_OVERRIDE_SUPPLY_AREA = 150.0
NDefines_Graphics.NGraphics.GRADIENT_BORDERS_THICKNESS_STRATEGIC_REGIONS = 150.0
-- HOD (user, 2026-10-16): the 3D models stay visible when zoomed out (vanilla removes map objects past 1100 and

-- shrinks city and building meshes from 180-220; the camera goes up to CAMERA_MAX_HEIGHT 3000). Trees keep vanilla's fade
-- (user: trees at a distance are not wanted).

-- a camera DISTANCE, not a height: tilted views and objects off the screen centre are farther than the camera is high
NDefines_Graphics.NGraphics.DRAW_MAP_OBJECTS_CUTOFF = 100000.0

NDefines_Graphics.NGraphics.FACILITY_DISTANCE_CUTOFF = 100000

NDefines_Graphics.NGraphics.CITY_SPRAWL_SHRINK_DISTANCE = 100000.0

NDefines_Graphics.NGraphics.MAP_BUILDINGS_SHRINK_DISTANCE = 100000
