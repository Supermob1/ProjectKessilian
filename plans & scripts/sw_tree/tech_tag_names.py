"""Per-faction tech names with the engine's built-in <TAG>_<tech> keys (vanilla does it: GER_infantry_at, SOV_support_weapons).

    python -B "plans & scripts/sw_tree/tech_tag_names.py"     (from the mod root)

Every tech in a visible tab gets <TAG>_<tech> and <TAG>_<tech>_desc for the Republic (REP, ALD) and the Separatist bloc.
Hardware techs take the faction's equipment name (<TAG>_<equipment>, hod_sw_faction_names_l_english.yml); the others take
NAMES below (Republic, Separatist[, Separatist desc]); anything else keeps its plain name for both.
Writes localisation/english/hod_sw_tech_tag_names_l_english.yml (UTF-8 with BOM).
"""
import glob, re

REP_TAGS, CIS_TAGS = ("REP", "ALD"), ("CIS", "CMG", "IBC", "TCU", "TDF", "XUC", "ZAL")
GAME = "F:/SteamLibrary/steamapps/common/Hearts of Iron IV/"
OUT = "localisation/english/hod_sw_tech_tag_names_l_english.yml"

S = lambda r, c, d=None: (r, c, d)
NAMES = {
    # infantry tab
    "imperial_thermal_detonator": S("Thermal Detonators", "Droid Thermal Detonators"),
    "blaster_efficiency1": S("Blaster Cooling I", "Mass-Produced Power Cells I"),
    "blaster_efficiency2": S("Blaster Cooling II", "Mass-Produced Power Cells II"),
    "blaster_efficiency3": S("Blaster Cooling III", "Mass-Produced Power Cells III"),
    "imperial_anti_tank": S("Infantry Anti-Armour Launchers", "E-60R Rocket Launchers",
                            "Shoulder-fired E-60R launchers give the droid line its own answer to walkers and tanks."),
    "small_repeater1": S("Clone Heavy Weapons I", "Droid Heavy Weapons I"),
    "medium_repeater1": S("Clone Heavy Weapons II", "Droid Heavy Weapons II"),
    "heavy_repeater1": S("Clone Heavy Weapons III", "Droid Heavy Weapons III"),
    "heavy_repeater2": S("Clone Heavy Weapons IV", "Droid Heavy Weapons IV"),
    "small_repeater2": S("Macrobinocular Visors I", "Droid Photoreceptors I", "Better photoreceptors let battle droids find and hit targets in the dark."),
    "medium_repeater2": S("Macrobinocular Visors II", "Droid Photoreceptors II", "Low-light and thermal receptors for the whole droid line."),
    "special_training": S("ARC Trooper Training", "Commando Droid Programming", "Selected droids are loaded with infiltration, demolition and independent-action routines."),
    "advanced_special_training": S("Clone Commando Training", "BX Commando Programming"),
    "improved_special_training": S("Accelerated Clone Conditioning", "Upgraded Droid Processors", "Faster processors make the droids react quicker and follow orders more reliably."),
    "advanced_special_training2": S("Elite Commando Squads", "Elite Commando Droid Squads"),
    "improved_special_training2": S("Gunship Assault Doctrine", "Dropship Assault Programming", "Droids are programmed to fight straight out of the landing craft."),
    "elite_troopers": S("ARC Veterans", "Tactical Droid Command", "Tactical droids take direct command of the best-equipped units."),
    # armour tab refits
    "tx130t": S("TX-130T Fighter Tank Refit", "AAT Refit Programme"),
    "mauler": S("Scout-class 2-M Repulsor Tank", "Scout Tank Droid Refit"),
    "imperial_tank": S("Repulsor Tank Refit", "Heavy Repulsor Refit"),
    "ammo_improvement2": S("Ammo Improvement II", "Ammo Improvement II", "Improved energiser chambers push the droids' power packs further still."),
    # special forces doctrine
    "special_forces_mountaineers": S("Clone Mountain Troopers", "Mountain Assault Droids"),
    "ski_troops": S("Cold Assault Troopers", "Cold-Weather Droid Plating"),
    "rangers": S("Rough Terrain Troopers", "All-Terrain Droid Chassis"),
    "special_forces_recon": S("Clone Scout Recon", "Probe Droid Recon"),
    "mountaineers_combat_1": S("Holding the Line", "Hold Position Protocols"),
    "mountaineers_combat_2": S("Mountain Artillery", "Mountain Artillery Droids"),
    "mountaineers_combat_3": S("Combined Arms Training", "Combined Arms Programming"),
    "mountaineers_keystone_1": S("Backbone of the Grand Army", "Backbone of the Droid Army"),
    "mountaineers_keystone_2": S("Shared Kaminoan Instructors", "Shared Tactical Databanks"),
    "special_forces_marines": S("Clone Marines", "Marine Droid Legions"),
    "marines_jungle_troops": S("Jungle Troopers", "Swamp and Jungle Droids"),
    "marines_shore_parties": S("Beachhead Parties", "Landing Droid Parties"),
    "marines_recon": S("Gruelling Training Regimen", "Combat Simulation Loops"),
    "marines_commandoes": S("Marine Commandos", "Marine Commando Droids"),
    "marines_expeditionary": S("Expeditionary Legions", "Expeditionary Droid Legions"),
    "marines_commandos_demolition": S("Demolition Troopers", "Demolition Droids"),
    "marines_expeditionary_blowtorch": S("Flame and Charge Tactics", "Flame and Charge Protocols"),
    "marines_commandoes_mechanised": S("Mechanised Marine Corps", "Mechanised Marine Droids"),
    "marines_expeditionary_support": S("Expeditionary Task Forces", "Expeditionary Battle Groups"),
    "special_forces_paratroopers": S("Gunship Assault Troopers", "Dropship Assault Droids",
                                     "Skies darkened by landing craft, each one disgorging a company of droids straight onto the objective."),
    "paras_dispersed_drop": S("Reconnaissance and Sabotage", "Infiltration and Sabotage Droids"),
    "paras_combat_drop": S("Combat Insertion", "Combat Drop Protocols"),
    "paras_airborne_light_armor": S("Gunship-Lifted Armour", "Dropship-Lifted Armour"),
    "paras_combat_1": S("Airborne Comms", "Airborne Signal Relays"),
    "paras_combat_2": S("Airborne Medics", "Airborne Repair Droids"),
    "paras_bonus_1": S("Enhanced Navigational Training", "Navigation Computers"),
    "paras_bonus_2": S("Strategic Lift Corps", "Droid Carrier Fleets"),
    "paras_keystone_1": S("Best of the Best", "Top-Line Units"),
    "paras_keystone_2": S("Backbone of the Grand Army", "Backbone of the Droid Army"),
    "special_forces_rangers": S("Clone Rangers", "Ranger Droids"),
    "rangers_jaegers_training": S("Old Republic Ranger Traditions", "Bounty Hunter Field Craft"),
    "rangers_jungle_training": S("Ranger Jungle Training", "Ranger Droid Jungle Routines"),
    "rangers_guerilla_doctrine": S("Forest Guerrillas", "Forest Ambush Protocols"),
    "rangers_recon_terrain_training": S("Ranger Terrain Mastery", "Terrain Mapping Subroutines"),
    "rangers_fire_support_integration": S("Fire Support Integration", "Fire Support Uplinks"),
    "rangers_urban_combat": S("Urban Combat Troopers", "Urban Combat Programming"),
    "elite_rangers_doctrine": S("Elite Rangers", "Elite Ranger Droids"),
    "rangers_backbone_doctrine": S("Light Infantry Specialisation", "Light Droid Specialisation"),
}
from base_tech_skin import NAMES as _BASE   # industry / engineering tabs (same tuple layout)
NAMES.update(_BASE)

TOK = re.compile(r'"[^"]*"|[{}=<>]|[^\s{}=<>"#]+|#[^\n]*')


def parse(text):
    toks = [t for t in TOK.findall(text) if not t.startswith("#")]
    pos = 0

    def block():
        nonlocal pos
        out = []
        while pos < len(toks):
            t = toks[pos]; pos += 1
            if t == "}":
                return out
            if t == "{":
                out.append((None, block()))
            elif pos < len(toks) and toks[pos] in "=<>":
                pos += 2
                v = toks[pos - 1]
                out.append((t, block() if v == "{" else v.strip('"')))
            else:
                out.append((None, t.strip('"')))
        return out
    return block()


def get(b, k):
    return [v for kk, v in b if kk == k]


def read(p):
    return open(p, encoding="utf-8-sig", errors="replace").read()


def main():
    loc = {}
    for p in glob.glob(GAME + "localisation/english/*.yml") + glob.glob("localisation/english/*.yml"):
        if p.replace("\\", "/").endswith(OUT):
            continue
        for m in re.finditer(r'^\s*([\w.\-]+):\d*\s*"(.*)"', read(p), re.M):
            loc[m.group(1)] = m.group(2)
    hidden = set()
    for p in glob.glob("common/technology_tags/*.txt"):
        for _, v in parse(read(p)):
            for fk, fb in (v if isinstance(v, list) else []):
                if isinstance(fb, list) and any(a == "available" and ("always", "no") in b for a, b in fb if isinstance(b, list)):
                    hidden.add(fk)
    lines, n = ["l_english:"], 0
    for p in sorted(glob.glob("common/technologies/*.txt")):
        for k, v in parse(read(p)):
            if k != "technologies":
                continue
            for t, tb in v:
                if not isinstance(tb, list) or not t or t.startswith("@"):
                    continue
                folders = [get(f, "name")[0] for f in get(tb, "folder")]
                allow = get(tb, "allow")
                if not folders or all(f in hidden for f in folders) or (allow and ("always", "no") in allow[0]):
                    continue
                eq = [e for b in get(tb, "enable_equipments") for _, e in b]
                base, bdesc = loc.get(t, t), loc.get(t + "_desc", "")
                for side, tags in ((0, REP_TAGS), (1, CIS_TAGS)):
                    if t in NAMES:
                        name = NAMES[t][side]
                        rdesc = NAMES[t][3] if len(NAMES[t]) > 3 else bdesc
                        desc = (NAMES[t][2] or rdesc) if side else rdesc
                    elif eq and f"{tags[0]}_{eq[0]}" in loc:
                        name, desc = loc[f"{tags[0]}_{eq[0]}"], loc.get(f"{tags[0]}_{eq[0]}_desc", bdesc)
                    else:
                        name, desc = base, bdesc
                    for tag in tags:
                        lines += [f' {tag}_{t}:0 "{name}"', f' {tag}_{t}_desc:0 "{desc}"']
                n += 1
    open(OUT, "w", encoding="utf-8-sig", newline="\n").write("\n".join(lines) + "\n")
    assert n > 200 and all('"' not in l.split('"', 1)[1][:-1] for l in lines[1:]), "unescaped quote or too few techs"
    print(n, "techs ->", OUT)


if __name__ == "__main__":
    main()
