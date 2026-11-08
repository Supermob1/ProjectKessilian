"""Per-faction tech names: Republic (default, from cw_map), Separatist, Independent.
Tech name/desc keys become [SWN_x]/[SWD_x] scripted loc. Order of the defined_text entries: CIS, IND, then REP with
no trigger, so if the tech screen ever lacks a country scope, players still see the Republic name.
Equipment: CIS_<equipment> tag-prefixed names (engine feature, CIS tag only).
shortcut: hod_sw_faction_names_l_english.yml has hand edits since (descs, HAG-M / HAML names); diff before rerunning."""
import os, re, glob, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cw_map import TECH, NAME, tech_blocks, enables

M = r"F:\Documents\Paradox Interactive\Hearts of Iron IV\mod\ProjectKessilian"
# tech: (Separatist name, Independent name)
F = {
    # air
    "laat": ("HMP Droid Gunship", "Armed Transport Gunship"), "maat": ("C-9979 Landing Craft", "Patrol Gunship"),
    "idt": ("Sheathipede-class Shuttle", "Armoured Shuttle"), "tie-rp": ("Droch-class Boarding Ship", "Assault Shuttle"),
    "aal": ("Heavy Droid Lander", "Assault Lander"), "torrent": ("Vulture Droid", "CloakShape Fighter"),
    "z-95": ("Belbullab-22 Starfighter", "Z-95 Headhunter"), "tie-rb": ("Droid Tri-Fighter", "Kihraxz Light Fighter"),
    "tie_fighter": ("I-Beam Fighter", "Fang Fighter"), "tie-sf": ("Heavy Droid Starfighter", "StarViper Heavy Fighter"),
    "v_wing": ("Nantex-class Starfighter", "R-41 Starchaser"), "tie-in": ("Mankvim-814 Interceptor", "M3-A Scyk Interceptor"),
    "tie-sk": ("Porax-38 Starfighter", "N-1 Starfighter"), "tie-vn": ("Droid Interceptor", "Fast Interceptor"),
    "tie-ba": ("Atmospheric Droid Fighter", "Atmospheric Strike Fighter"), "arc-170": ("Rogue-class Starfighter", "G-1A Heavy Starfighter"),
    "tie_defender": ("Droid Super-Fighter", "Prototype Heavy Fighter"), "y-wing": ("Hyena-class Droid Bomber", "BTL-A4 Y-wing"),
    "skipray": ("Sabaoth Bomber", "GAT-12 Skipray Blastboat"), "tie-sa": ("Heavy Hyena Bomber", "Heavy Strike Bomber"),
    "scimitar": ("Droid Strike Bomber", "Assault Bomber"),
    # artillery
    "mortar": ("Droid Mortar Teams", "Mortar Teams"), "spha": ("HAG Heavy Artillery Gun", "Heavy Artillery Walker"),
    "spma": ("Corporate Alliance Artillery Droid", "Turbolaser Artillery"), "atap": ("OG-9 Homing Spider Droid", "Siege Walker"),
    "av7": ("Separatist Proton Cannon", "Antivehicle Cannon"), "rx": ("Droid Anti-Air Battery", "Anti-Air Fighting Vehicle"),
    "ataa": ("Hailfire Riot Control Droid", "Anti-Air Walker"),
    # infantry
    "republic_weapon1": ("E-5 Blaster Rifle", "Merr-Sonn Blaster Rifles"), "imperial_weapons": ("E-5C Heavy Blaster Rifle", "EE-3 Carbine Rifle"),
    "imperial_weapons2": ("E-5s Sniper Rifle", "Heavy Blaster Rifles"), "firstorder_weapons": ("E-5 Mk II Blaster", "A280 Blaster Rifle"),
    "special_training": ("Droid Combat Programming", "Mercenary Training"), "advanced_special_training": ("BX Commando Droids", "Mandalorian Veterans"),
    "improved_special_training": ("Droid Brain Upgrades", "Combat Stims"), "advanced_special_training2": ("IG-100 MagnaGuards", "Bounty Hunter Squads"),
    "improved_special_training2": ("Droid Gunship Drops", "Jetpack Assault Doctrine"), "elite_troopers": ("Super Battle Droid Legions", "Elite Mercenaries"),
    "atot": ("MTT Multi-Troop Transport", "Open Troop Walker"), "rtt": ("Droid Troop Carrier", "Armoured Troop Transport"),
    "itt": ("Heavy MTT", "Heavy Troop Transport"), "itc": ("Droid Troop Carrier Mk II", "Troop Carrier"),
    "juggernaut": ("Corporate Alliance Troop Hauler", "Heavy Wheeled Transport"), "isp": ("Droid Support Platform", "Support Platform"),
    "barc": ("STAP Speeder", "Speeder Bike"), "ava": ("Advanced STAP", "Armed Speeder"), "z_speeder": ("Armed STAP", "Light Speeder"),
    # armour
    "republic_tank": ("AAT Battle Tank", "Repulsor Battle Tank"), "tx130t": ("GAT Ground Armoured Tank", "Fighter Tank"),
    "repulsor": ("NR-N99 Persuader Tank Droid", "Heavy Hover Tank"), "h_repulsor": ("Confederate Super Tank", "Heavy Repulsor Tank"),
    "mauler": ("AAT Mk II Battle Tank", "Occupation Tank"), "px": ("GAT Ground Armoured Tank", "Assault Tank"),
    "crawler": ("Droid Fighter Tank", "Repulsor Strike Tank"),   # imperial_tank: refit, no equipment (own name)
    "atrt": ("DSD1 Dwarf Spider Droid", "Scout Walker"), "atrct": ("LM-432 Crab Droid", "Recon Walker"),
    "atpt": ("Espo Walker", "Personal Walker"), "atdp": ("Vulture Droid Walker", "Light Scout Walker"),
    "atst": ("LR-57 Combat Droid", "Patrol Walker"), "foatst": ("Heavy Spider Droid", "Heavy Scout Walker"),
    "atte": ("OG-9 Homing Spider Droid", "Six-Legged Assault Walker"), "utat_tech": ("IG-227 Hailfire Droid", "Heavy Gun Walker"),
    "atat_tech": ("Octuptarra Magna Tri-Droid", "Heavy Assault Walker"), "elite_atat_tech": ("Protodeka Heavy Droid", "Armoured Assault Walker"),
    "fo_atat_tech": ("Class I Defence Droid", "Cargo Walker"), "atm6": ("Droid Assault Walker", "Siege Walker Mk II"),
    # starships
    "imp_tech_dd_1": ("Pursuer-class Enforcement Ship", "Patrol Corvette"), "imp_tech_dd_2": ("Diamond-class Cruiser", "Escort Frigate"),
    "imp_tech_dd_3": ("Droid Picket Ship", "Raider Corvette"), "imp_tech_cl_1": ("Munificent-class Star Frigate", "Light Cruiser"),
    "imp_tech_cl_2": ("Recusant-class Light Destroyer", "Corellian Gunship"), "imp_tech_cl_3": ("Separatist Light Destroyer", "Strike Cruiser"),
    "imp_tech_ca_1": ("Providence-class Destroyer", "Assault Cruiser"), "imp_tech_ca_2": ("Providence-class Dreadnought", "Heavy Cruiser"),
    "imp_tech_ca_3": ("Bulwark Mk I Battlecruiser", "Battlecruiser"), "imp_tech_bb_1": ("Lucrehulk-class Battleship", "Dreadnaught Heavy Cruiser"),
    "imp_tech_bb_2": ("Subjugator-class Heavy Cruiser", "Star Dreadnought"), "imp_tech_bb_3": ("Bulwark Mk III Battlecruiser", "Capital Battleship"),
    "imp_tech_cv_1": ("Lucrehulk-class Droid Control Ship", "Escort Carrier"), "imp_tech_cv_2": ("Providence-class Carrier", "Fleet Carrier"),
    "imp_tech_cv_3": ("Core Ship Carrier", "Heavy Carrier"), "imp_tech_ss_1": ("Cloaked Droid Picket", "Smuggler Stealth Ship"),
    "imp_tech_ss_2": ("Stealth Droid Frigate", "Cloaked Raider"), "imp_tech_ss_3": ("Cloaked Droid Raider", "Stealth Frigate"),
}
assert not set(F) - set(TECH), set(F) - set(TECH)

# Built-in per-country names (vanilla style): equipment techs carry no name of their own, the tech screen
# shows the unlocked equipment's name, and equipment keys take a TAG_ prefix. Default = independent.
REP_TAGS = ["REP", "ALD"]
CIS_TAGS = ["CIS", "CMG", "IBC", "TCU", "TDF", "XUC", "ZAL"]
NEUTRAL_TRAINING = {  # no equipment -> no per-country hook; one shared name
    "special_training": "Special Training", "advanced_special_training": "Commando Training",
    "improved_special_training": "Advanced Conditioning", "advanced_special_training2": "Elite Commando Squads",
    "improved_special_training2": "Airborne Assault Doctrine", "elite_troopers": "Elite Troopers"}


def desc(name, side):
    return {"CIS": f"{name}, built by the Separatist droid foundries for the Confederacy's war.",
            "IND": f"{name}, built or bought by worlds that answer to neither Republic nor Confederacy.",
            "REP": None}[side]


BLOCKS = {k: v for f in glob.glob(os.path.join(M, "common", "technologies", "hod_sw_*.txt")) for k, v in tech_blocks(open(f, encoding="utf-8").read()).items()}
p = os.path.join(M, "localisation", "english", "hod_sw_tech_l_english.yml")
base = {}
for l in open(p, encoding="utf-8-sig").read().split("\n")[1:]:
    m = re.match(r'\s*([\w\-\.]+):\d*\s*"(.*)"\s*$', l)
    if m:
        base[m.group(1)] = m.group(2)
tagged, done = [], set()
for t, (cis, ind) in F.items():
    if t in NEUTRAL_TRAINING:
        base[t] = NEUTRAL_TRAINING[t]
        continue
    eqs = enables(BLOCKS.get(t, ""))
    assert eqs, t
    rep_n, rep_d, _ = TECH[t]
    base.pop(t, None); base.pop(t + "_desc", None)          # tech shows its equipment's (per-country) name
    for i, eq in enumerate(eqs):
        if eq in done:
            continue
        done.add(eq)
        gun = eq == "laati_equipment" or eq.endswith("_gunship_equipment")
        pair = len([e for e in eqs if not e.startswith("ship_hull")]) > 1

        def variant(n):  # transport/gunship pairs: "X Dropship" + "X Gunship"
            if not pair:
                return n
            stem = n[:-8] if n.endswith(" Gunship") else n
            return stem + (" Gunship" if gun else " Dropship")
        names = {"IND": variant(ind), "CIS": variant(cis), "REP": NAME.get(eq, rep_n) if i else rep_n}
        descs = {"IND": desc(ind, "IND"), "CIS": desc(cis, "CIS"), "REP": rep_d}
        base[eq], base[eq + "_desc"] = names["IND"], descs["IND"]
        if eq.startswith("ship_hull"):
            base[eq + "_short"] = names["IND"].split("-class")[0]
        for side, tags in (("REP", REP_TAGS), ("CIS", CIS_TAGS)):
            for tag in tags:
                tagged.append(f' {tag}_{eq}:0 "{names[side]}"')
                tagged.append(f' {tag}_{eq}_desc:0 "{descs[side]}"')
                if eq.startswith("ship_hull"):
                    tagged.append(f' {tag}_{eq}_short:0 "{names[side].split("-class")[0]}"')
open(p, "w", encoding="utf-8-sig", newline="\n").write("l_english:\n" + "".join(f' {k}:0 "{v}"\n' for k, v in base.items()))
open(os.path.join(M, "localisation", "english", "hod_sw_faction_names_l_english.yml"), "w", encoding="utf-8-sig", newline="\n").write(
    "l_english:\n" + "\n".join(tagged) + "\n")
for f in ("common/scripted_triggers/HOD_sw_faction_triggers.txt", "common/scripted_localisation/HOD_sw_tech_names.txt"):
    if os.path.exists(os.path.join(M, f)):
        os.remove(os.path.join(M, f))
print("techs:", len(F), "| equipment named per faction:", len(done), "| tagged lines:", len(tagged))
