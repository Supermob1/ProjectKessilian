"""Alternate 3D models for the "Create Variant -> Select Model" picker (user 2026-11-11): the FotR / RaW / Thrawn's Revenge
models the user kept on the review page (alt_new.py), per hull line / land or plane archetype. Nothing else (user: those are all).

    python -B "plans & scripts/sw_tree/alt_models.py" renderlist   -> name=glb pairs still missing an icon (tech_icon_render.py)
    python -B "plans & scripts/sw_tree/alt_models.py"              -> writes the three files below

gfx/interface/equipmentdesigner/graphic_db/hod_sw_alt_models.txt: per country tag (+ default) and equipment TYPE a top
pool with the type's current icon + entity (so default designs keep today's look), then one pool per alternate model
on the ARCHETYPE (own faction's models first). interface/hod_sw_alt_model_icons.gfx: GFX_hod_alt_<model>_medium.
gfx/entities/zz_hod_sw_alt_models.asset: hod_alt_<model>_entity clones with the unit's map scale.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
os.chdir(MOD)
import naval_tree as N            # noqa: E402
import unit_models_sw as U        # noqa: E402
import alt_new                    # noqa: E402

ICON_DIR = "gfx/interface/technologies/hod_alt"

# land archetype -> the sub-unit whose map model it drives
LAND_ARCH = {"light_equipment": "light_vehicle", "extra_light_equipment": "scoutwalker", "speeder_equipment": "speeder",
             "heavy_equipment": "heavy_vehicle", "assault_equipment": "assault_vehicle", "mobile_art_equipment": "mobile_artillery",
             "mobile_aa_equipment": "mobile_anti_air", "troop_transport_equipment": "armored_troop_transport",
             "heavy_troop_transport_equipment": "heavy_armored_troop_transport"}
PLANE_ARCH = ("imp_fighter_equipment", "imp_defender_equipment", "imp_interceptor_equipment", "imp_bomber_equipment",
              "imperial_transport_plane_equipment", "imp_gunship_equipment")
SHIP_ARCH = {line: v[0] for line, v in N.LINES.items()}

SPEEDER_SCALE = 1.5   # speeders are scaled x1.5 next to the tanks (unit_models_sw.py)


def ent_key(entity):
    return entity[:-len("_entity")] if entity.endswith("_entity") else entity


def catalog():
    """{kind: [(model key, side, scale)]}: only the models the user kept on the review page (alt_new.py, 2026-11-11);
    each equipment type's own current model is added separately by type_pools()"""
    cat = {}
    for kind, lst in alt_new.KEEP.items():
        for key, side in lst:
            if os.path.exists("gfx/models/units/hod_walkers/%s.mesh" % alt_new.model(key)):   # skip a failed conversion
                cat.setdefault(kind, []).append((alt_new.model(key), side, SPEEDER_SCALE if kind == "speeder_equipment" else 1.0))
    return cat


def equipment_archetypes():
    out = {}
    for f in ("hod_sw_zz_imperial_land_vehicle.txt", "hod_sw_imperial_airframe.txt"):
        s = open("common/units/equipment/" + f, encoding="utf-8-sig").read()
        for m in re.finditer(r"\n\t([a-z0-9_\-]+)\s*=\s*\{(.*?)\n\t\}", s, re.S):
            a = re.search(r"\barchetype\s*=\s*([a-z0-9_\-]+)", m.group(2))
            lvl = re.search(r"\bvisual_level\s*=\s*(\d+)", m.group(2))
            if a:
                out[m.group(1)] = (a.group(1), int(lvl.group(1)) if lvl else 0)
    return out


EQ = equipment_archetypes()


def sprites():
    names = set()
    for root, _, files in os.walk("interface"):
        for f in files:
            if f.endswith(".gfx"):
                names |= set(re.findall(r'name\s*=\s*"(GFX_[^"]+)"', open(os.path.join(root, f), encoding="utf-8-sig", errors="ignore").read()))
    return names


def icon_file(model):
    if model.startswith("hod_ship_") and os.path.exists("gfx/interface/technologies/hod_render/ship_%s_medium.dds" % model[9:]):
        return "gfx/interface/technologies/hod_render/ship_%s_medium.dds" % model[9:]
    return "%s/%s_medium.dds" % (ICON_DIR, model)


def land_entity(scope, unit, level):
    """the entity the engine shows today for this sub-unit / visual level (unit_models_sw.py names)"""
    table = U.LAND.get(scope, U.IND)
    lv = table.get(unit, {})
    return "%s_%s_%d_entity" % (scope, unit, level) if level in lv and level != 1 else "%s_%s_entity" % (scope, unit)


def entities():
    names = set()
    for root, _, files in os.walk("gfx/entities"):
        for f in files:
            if f.endswith((".asset", ".gfx")):
                names |= set(re.findall(r'name\s*=\s*"([^"]+_entity)"', open(os.path.join(root, f), encoding="utf-8-sig", errors="ignore").read()))
    return names


ENTS = set()


def type_pools(scope, side, have):
    """top pools: each equipment type keeps its current icon + model"""
    out = []
    tag = scope if scope != "default" else None

    def pool(key, icon, model, weight=100):
        if icon not in have:
            icon = "GFX_%s_medium" % key if "GFX_%s_medium" % key in have else None   # tag without its own sprite: generic one
        if model not in ENTS:
            model = None
        if not (icon or model):
            return
        out.append("\t%s = {\n\t\tpool = {\n\t\t\tweight = %s\n%s%s\t\t}\n\t}" % (
            key, weight, "\t\t\ticons = { %s }\n" % icon if icon else "", "\t\t\tmodels = { %s }\n" % model if model else ""))
    gfxscope = tag or "western_european_gfx"
    for eq, (arch, level) in EQ.items():
        if arch in LAND_ARCH:
            pool(eq, "GFX_%s_%s_medium" % (tag, eq) if tag else "GFX_%s_medium" % eq, land_entity(gfxscope, LAND_ARCH[arch], level))
        elif arch in PLANE_ARCH:
            pool(eq, "GFX_%s_%s_medium" % (tag, eq) if tag else "GFX_%s_medium" % eq, "%s_%s_entity" % (gfxscope, eq))
    for line, tier, year, parents, cost, stats, gen, rep, cis in N.SHIPS:
        e = N.eq(line, tier)
        model = "hod_ship_%s_entity" % (cis if side == "c" else rep)[1]
        pool(e, "GFX_%s_%s_medium" % (tag, e) if tag else "GFX_%s_medium" % e, model)
    return out


def alt_pools(cat, side):
    out = []
    for kind, models in cat.items():
        arch = SHIP_ARCH.get(kind, kind)
        pools = []
        for model, mside, scale in models:
            w = 2 if mside == side else 1   # own faction's models listed first
            pools.append("\t\tpool = { weight = %d icons = { GFX_hod_alt_%s_medium } models = { %s } }" % (w, model, alt_entity(model, scale)))
        out.append("\t%s = {\n%s\n\t}" % (arch, "\n".join(pools)))
    return out


def alt_entity(model, scale):
    return "hod_alt_%s_entity" % model[4:] if scale != 1.0 else model + "_entity"


def renderlist():
    pairs = []   # rendered from the game mesh (unit_models.py output): some SPECS sources are folders / rigs
    for kind, models in catalog().items():
        for model, _, _ in models:
            mesh = "gfx/models/units/hod_walkers/%s.mesh" % model
            if not os.path.exists(icon_file(model)) and os.path.exists(mesh):
                pairs.append("%s=%s" % (model, mesh))
    print(" ".join(sorted(set(pairs))))


def main():
    cat = catalog()
    have = sprites()
    ENTS.update(entities())
    blocks = ["# generated by plans & scripts/sw_tree/alt_models.py - alternate models for the variant 'Select Model' picker"]
    scopes = [(t, "r") for t in N.REP_TAGS] + [(t, "c") for t in N.CIS_TAGS] + [("FLT", "r"), ("default", "r")]
    for scope, side in scopes:
        blocks.append("%s = {\n%s\n%s\n}" % (scope, "\n".join(type_pools(scope, side, have)), "\n".join(alt_pools(cat, side))))
    open("gfx/interface/equipmentdesigner/graphic_db/hod_sw_alt_models.txt", "w", encoding="utf-8", newline="\n").write("\n\n".join(blocks) + "\n")
    gfx, ents, missing = [], [], []
    seen = set()
    for kind, models in cat.items():
        for model, _, scale in models:
            if not os.path.exists(icon_file(model)):
                missing.append(model)
            if model not in seen:
                seen.add(model)
                gfx.append('\tspriteType = { name = "GFX_hod_alt_%s_medium" texturefile = "%s" }' % (model, icon_file(model)))
            if scale != 1.0 and "hod_alt_%s" % model[4:] not in seen:
                seen.add("hod_alt_%s" % model[4:])
                ents.append('entity = { name = "%s" clone = "%s_entity" scale = %s }' % (alt_entity(model, scale), model, scale))
    open("interface/hod_sw_alt_model_icons.gfx", "w", encoding="utf-8", newline="\n").write(
        "# generated by plans & scripts/sw_tree/alt_models.py\nspriteTypes = {\n" + "\n".join(gfx) + "\n}\n")
    open("gfx/entities/zz_hod_sw_alt_models.asset", "w", encoding="utf-8", newline="\n").write(
        "# generated by plans & scripts/sw_tree/alt_models.py - scaled clones for the variant model picker\n" + "\n".join(ents) + "\n")
    print("kinds", len(cat), "models", len(seen), "scaled", len(ents), "missing icons", missing)


if __name__ == "__main__":
    renderlist() if sys.argv[1:] == ["renderlist"] else main()
