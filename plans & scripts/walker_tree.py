"""Turn the armour tab (NSB_armor.txt) into the walker tree: each chassis tech hands out walker chassis and walker
battalions instead of tanks; repulsor tanks become support companies on the light line. One-off, run from the mod root.

    python "WIPGFX/plans & scripts/walker_tree.py"
"""
import re

PATH = "common/technologies/NSB_armor.txt"
ROLES = ("aa", "artillery", "destroyer", "flame")


def chassis(size, n):
    """walker chassis variant n of a size, with its role versions (x_walkers_chassis.txt naming)"""
    base = "walker_chassis" if size == "light" else f"walker_chassis_{size}"
    pre = "walker" if size == "light" else f"walker_{size}"
    return [f"{base}_{n}"] + [f"{pre}_{r}_chassis_{n}" for r in ROLES]


def units(size):
    if size == "light":
        return ["walkers_light", "walkers_light_recon", "walkers_light_artillery", "walkers_light_destroyer",
                "walkers_light_aa", "walkers_flame", "walkers_light_support_aa", "walkers_light_support_destroyer"]
    u = [f"walkers_{size}", f"walkers_{size}_artillery", f"walkers_{size}_destroyer", f"walkers_{size}_aa",
         f"walkers_{size}_flame"]
    if size != "super_heavy":
        u += [f"walkers_{size}_support_aa", f"walkers_{size}_support_destroyer"]
    return u


# tech -> (equipment, battalions, modules, repulsor stats bonus)
PLAN = {
    "gwtank_chassis": (chassis("light", 0) + ["walker_sponson_chassis_0"], units("light"), ["walker_pneumatic_damper"]),
    "basic_light_tank_chassis": (chassis("light", 1) + ["walker_sponson_chassis_1", "repulsor_tank_equipment_1"],
                                 ["repulsor_tank_company"], []),
    "improved_light_tank_chassis": (chassis("light", 2) + ["walker_sponson_chassis_2", "repulsor_tank_equipment_2"],
                                    [], ["walker_fixed_sponson_turret"]),
    "advanced_light_tank_chassis": (["repulsor_tank_equipment_3"], [], []),
    "basic_medium_tank_chassis": (chassis("medium", 0), units("medium"), ["walker_hydropneumatic_recuperator"]),
    "improved_medium_tank_chassis": (chassis("medium", 1), [], ["walker_oscillating_autoloader"]),
    "advanced_medium_tank_chassis": (chassis("medium", 2), [], []),
    "basic_heavy_tank_chassis": (chassis("heavy", 0), units("heavy"), []),
    "improved_heavy_tank_chassis": (chassis("heavy", 1), [], []),
    "advanced_heavy_tank_chassis": (chassis("heavy", 2), [], []),
    "main_battle_tank_chassis": (chassis("modern", 0), units("modern"), []),
    "super_heavy_tank_chassis": (chassis("super_heavy", 0) + ["walker_chassis_land_cruiser_1"],
                                 units("super_heavy") + ["walker_land_cruiser"],
                                 ["walker_lc_load_frame", "walker_lc_800mm_bombard"]),
}
TEMPLATE = """		# HOD: hand the country a walker template (history/units/HOD_unlock_walkers.txt)
		on_research_complete_limit = {
			NOT = { has_template_containing_unit = walkers_light }
		}
		on_research_complete = {
			hidden_effect = { load_oob = "HOD_unlock_walkers" }
			custom_effect_tooltip = UNLOCK_DIVISION_TEMPLATE
		}
"""


def span(s, key, start, end):
    m = re.compile(r"\n\t\t%s\s*=\s*\{" % key).search(s, start, end)
    if not m:
        return None
    i, d = m.end(), 1
    while d:
        d += {"{": 1, "}": -1}.get(s[i], 0)
        i += 1
    return m.start(), i


def lst(key, items):
    return f"\n\t\t{key} = {{\n" + "".join(f"\t\t\t{x}\n" for x in items) + "\t\t}"


def patch(s):
    for tech, (eq, un, mods) in PLAN.items():
        m = re.search(r"^\t%s\s*=\s*\{[^\n]*\n" % tech, s, re.M)
        assert m, tech
        a = m.end()
        end = re.search(r"^\t\}", s[a:], re.M).start() + a
        block = s[a:end]
        b = "\n" + block
        # drop the tank unlocks and the tank-era research effects (vanilla templates, Italian/Hungarian scripts
        # whose country checks were commented out and so fired for everyone)
        for key in ("enable_equipments", "enable_subunits", "on_research_complete_limit", "on_research_complete"):
            while True:
                sp = span(b, key, 0, len(b))
                if not sp:
                    break
                b = b[:sp[0]] + b[sp[1]:]
        head = lst("enable_equipments", eq)
        if un:
            head += lst("enable_subunits", un)
        mspan = span(b, "enable_equipment_modules", 0, len(b))
        if mods and mspan:
            inner = b[mspan[0]:mspan[1]]
            inner = inner[:inner.rfind("}")] + "".join(f"\t\t\t{x}\n" for x in mods) + "\t\t}"
            b = b[:mspan[0]] + inner + b[mspan[1]:]
        elif mods:
            head += lst("enable_equipment_modules", mods)
        if tech == "gwtank_chassis":
            head += "\n" + TEMPLATE.rstrip("\n")
        s = s[:a] + "\t\t# HOD: walker tree (walker_tree.py): walker chassis replace the tanks" + head + b[1:] + s[end:]
    return s


raw = open(PATH, "rb").read()
bom = raw.startswith(b"\xef\xbb\xbf")
s = raw.decode("utf-8-sig")
crlf = "\r\n" in s
s = patch(s.replace("\r\n", "\n"))
c = re.sub(r"#[^\n]*", "", s)
assert c.count("{") == c.count("}"), "unbalanced"
open(PATH, "wb").write((b"\xef\xbb\xbf" if bom else b"") + (s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
print("armour tree patched:", len(PLAN), "techs")
