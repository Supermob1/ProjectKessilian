"""Felucia's states, map positions and the Felucian tribes, on the provinces drawn by felucia_map.py.

    python "WIPGFX/plans & scripts/felucia_tribes.py"            states, names, victory points, buildings.txt,
                                                                 unitstacks.txt, airports, rails, supply, lanes, country
    python "WIPGFX/plans & scripts/felucia_tribes.py" country    only the FLT country files

Zones (WIPGFX/Assets/felucia_zones.json): every red lowland is a Commerce Guild state, with the passages that touch it;
the two blue mountain jungles are the tribes' (FLT); the rest is impassable jungle, owned with Kway Teow. The tribes
start at peace and launch border wars on the Guild's lowlands when they can.
Run order: felucia_map.py -> felucia_tribes.py -> planet_terrain_gen.py --felucia -> --globe-texture
-> faction_templates.py.
"""
import csv, glob, json, math, os, re, sys
import numpy as np

TRIBES, GUILD = "FLT", "CMG"
ZONES_JSON = "WIPGFX/Assets/felucia_zones.json"
REGION = "map/strategicregions/81-Felucia.txt"
RED_IDS = [80, 715, 717, 718, 713, 719]        # the capital (central lowland) first
BLUE_IDS = {"west": 714, "east": 716}
WHITE_FIRST = 1123                              # impassable jungle states from here
CAPITAL = 80
# lowland names by compass direction from the planet's centre (name_lore.py); the capital is the central one
# Names. Guild land: the canon cities (Wookieepedia: capital Kway Teow with the Commerce Guild headquarters outside
# its walls, Har Gau, Niango, Akira, Jiaozi, the Nigkoe Detention Facility) as corporate holdings. Native land: the
# Ancient Abyss (Legends: the Felucians' sacred sarlacc pit) and invented names in a Vietnamese vein, unaccented
# because the game's fonts lack Vietnamese diacritics (nui da voi = limestone mountain, ban nam = mushroom village...)
RED_NAMES = {"centre": ("Kway Teow", "Kway Teow"), "n": ("Niango Plantation Zone", "Niango"),
             "ne": ("Niango Plantation Zone", "Niango"), "e": ("Akira Guild Holding", "Akira"),
             "se": ("Akira Guild Holding", "Akira"), "s": ("Jiaozi Trade Concession", "Jiaozi"),
             "sw": ("Har Gau Processing Zone", "Har Gau"), "w": ("Har Gau Processing Zone", "Har Gau"),
             "nw": ("Nigkoe Security District", "Nigkoe Detention Facility")}
BLUE_NAMES = {714: ("Nui Da Voi Highlands", "Ban Nam"), 716: ("Ancient Abyss", "Ancient Abyss")}
WHITE_NAMES = ["Rung Tham Deepwood", "Thach Lam Spires", "Dam Lay Mire", "Suong Mu Canopy", "Hang Dong Wilds",
               "Suoi Ngan Wilds", "Thac Bac Wilds", "Nui Xanh Wilds", "Rung Sau Wilds"]
# state-level building positions per state (as the game's own map has them), province-level ones per province
STATE_BUILDINGS = {"arms_factory": 6, "industrial_complex": 6, "anti_air_building": 3, "air_base": 1,
                   "stronghold_network": 1, "synthetic_refinery": 1, "fuel_silo": 1, "radar_station": 1,
                   "nuclear_reactor_spawn": 1, "rocket_site_spawn": 1}
PROVINCE_BUILDINGS = ("supply_node", "bunker", "special_project_facility_spawn")
COAST_BUILDINGS = ("coastal_bunker", "naval_supply_hub", "naval_headquarters", "naval_base_spawn", "floating_harbor")
WEATHER = """	weather={
		period={
			between={ 0.0 30.11 }
			temperature={ 22.0 38.0 }
			no_phenomenon=0.300
			rain_light=0.600
			rain_heavy=0.500
			snow=0.000
			blizzard=0.000
			arctic_water=0.000
			mud=0.000
			sandstorm=0.000
			min_snow_level=0.000
		}
	}"""


def rw(path, fn):
    raw = open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    s = raw.decode("utf-8-sig")
    crlf = "\r\n" in s
    s = fn(s.replace("\r\n", "\n"))
    c = re.sub(r"#[^\n]*", "", s)
    assert c.count("{") == c.count("}"), path
    open(path, "wb").write((b"\xef\xbb\xbf" if bom else b"") + (s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))


def state_files():
    return {int(re.search(r"\bid\s*=\s*(\d+)", open(f, encoding="utf-8-sig").read()).group(1)): f
            for f in glob.glob("history/states/*Felucia*.txt")}


def block(s, key):
    m = re.search(rf"\n\s*{key}\s*=\s*\{{", s)
    if not m:
        return ""
    i, d = m.end(), 1
    while d:
        d += {"{": 1, "}": -1}.get(s[i], 0)
        i += 1
    return s[m.start():i]


def compass(dy, dx):
    if math.hypot(dy, dx) < 18:
        return "centre"
    a = math.degrees(math.atan2(-dy, dx)) % 360          # 0 = east, counter-clockwise, map rows grow southward
    return ["e", "ne", "n", "nw", "w", "sw", "s", "se"][int(((a + 22.5) % 360) // 45)]


def plan_states(z, pid, fel):
    """state id -> dict(kind, provinces, name, vp names); passages join the red state they touch most"""
    from scipy import ndimage as ndi
    prov = {int(p): v for p, v in z["provinces"].items()}
    groups = {}
    for p, v in prov.items():
        groups.setdefault(v["group"], []).append(p)
    ys, xs = np.nonzero(fel)
    cy, cx = ys.mean(), xs.mean()
    gcentre = {g: np.mean([prov[p]["centre"] for p in ps], 0) for g, ps in groups.items()}
    kind = {g: prov[ps[0]]["zone"] for g, ps in groups.items()}
    reds = sorted([g for g in groups if kind[g] == "red"], key=lambda g: math.hypot(*(gcentre[g] - [cy, cx])))
    gmask = lambda g: np.isin(pid, groups[g])
    states, used_names = {}, set()
    for sid, g in zip(RED_IDS, reds):
        d = compass(*(gcentre[g] - [cy, cx]))
        name, vp = RED_NAMES["centre" if sid == CAPITAL else d]
        if name in used_names:
            name, vp = f"{name} ({d.upper()})", f"{vp} {d.upper()}"
        used_names.add(name)
        states[sid] = dict(kind="red", groups=[g], name=name, vp=vp)
    for g in [g for g in groups if kind[g] == "blue"]:
        sid = BLUE_IDS["west" if gcentre[g][1] < cx else "east"]
        states[sid] = dict(kind="blue", groups=[g], name=BLUE_NAMES[sid][0], vp=BLUE_NAMES[sid][1])
    red_of = {g: sid for sid, st in states.items() if st["kind"] == "red" for g in st["groups"]}
    for g in [g for g in groups if kind[g] == "corridor"]:          # passage -> red state with the longest border
        ring = ndi.binary_dilation(gmask(g), iterations=1) & ~gmask(g)
        touch = {}
        for rg, sid in red_of.items():
            touch[sid] = int((ring & gmask(rg)).sum())
        best = max(touch, key=touch.get)
        if touch[best] == 0:                                        # blue-to-white only: the nearest red state
            best = min(red_of.values(), key=lambda s: math.hypot(*(gcentre[g] - gcentre[states[s]["groups"][0]])))
        states[best]["groups"].append(g)
    whites = sorted([g for g in groups if kind[g] == "white"], key=lambda g: -len(groups[g]))
    for i, g in enumerate(whites):
        states[WHITE_FIRST + i] = dict(kind="white", groups=[g], name=WHITE_NAMES[i % len(WHITE_NAMES)], vp=None)
    for st in states.values():
        st["provinces"] = sorted(p for g in st["groups"] for p in groups[g])
    return states, prov


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from felucia_map import felucia_mask
    z = json.load(open(ZONES_JSON))
    land, pid, fel = felucia_mask()
    H, W = pid.shape
    states, prov = plan_states(z, pid, fel)
    rng = np.random.default_rng(716)
    old = state_files()
    fel_ids = set(old) | set(states)
    # ── states ──
    vps, names, vp_names = {}, {}, {}
    for sid, st in states.items():
        provs = st["provinces"]
        inner = [p for p in provs if prov[p]["zone"] != "corridor"]
        cen = np.mean([prov[p]["centre"] for p in inner], 0)
        main_p = min(inner, key=lambda p: math.hypot(*(np.array(prov[p]["centre"]) - cen)))
        if st["kind"] == "red":
            vps[sid] = [(main_p, 5 if sid == CAPITAL else 2)]
            vp_names[main_p] = st["vp"]
            if sid == CAPITAL:
                port = max([p for p in inner if p != main_p], key=lambda p: math.hypot(*(np.array(prov[p]["centre"]) - cen)))
                vps[sid].append((port, 3))
                vp_names[port] = "Commerce Guild Headquarters"
        elif st["kind"] == "blue":
            vps[sid] = [(main_p, 3)]
            vp_names[main_p] = st["vp"]
        st["main"] = main_p
        st["coastal"] = [p for p in provs if prov[p]["coastal"]]
        names[sid] = st["name"]
        src = open(old[sid], encoding="utf-8-sig").read() if sid in old else ""
        res = block(src, "resources") or "\n\tresources={\n\t}"
        if st["kind"] == "white":
            bld = "\n\t\tbuildings = {\n\t\t\tinfrastructure = 0\n\t\t}"
            man, cat = 6000, "wasteland_sector"
        else:
            bld = block(block(src, "history"), "buildings") or "\n\t\tbuildings = {\n\t\t\tinfrastructure = 2\n\t\t}"
            bld = re.sub(r"\n\s*\d+\s*=\s*\{[^{}]*\}", "", bld)                    # province buildings (ports) go
            if st["kind"] == "red" and st["coastal"]:
                port = max(st["coastal"], key=lambda p: -math.hypot(*(np.array(prov[p]["centre"]) - cen)))
                bld = bld.rstrip().rstrip("}") + f"\t\t\t{port} = {{\n\t\t\t\tnaval_base = 2\n\t\t\t}}\n\t\t}}"
            man = int(re.search(r"manpower\s*=\s*(\d+)", src).group(1)) if src else 50000
            cat = re.search(r"state_category\s*=\s*(\w+)", src).group(1) if src else "wasteland_sector"
        owner = TRIBES if st["kind"] == "blue" else GUILD
        cores = f"\t\tadd_core_of = {TRIBES}\n" + (f"\t\tadd_core_of = {GUILD}\n" if st["kind"] != "blue" else "")
        vp_txt = "".join(f"\t\tvictory_points = {{\n\t\t\t{p} {v}\n\t\t}}\n" for p, v in vps.get(sid, []))
        imp = f"\timpassable = yes\n\tforce_link_ownership_to = {CAPITAL}\n" if st["kind"] == "white" else ""
        text = (f"state={{\n\tid={sid}\n\tname=\"STATE_{sid}\"\n\t# HOD: Felucia, {st['kind']} zone (felucia_tribes.py)\n{imp}"
                f"\tprovinces={{\n\t\t{' '.join(map(str, provs))}\n\t}}\n{res.strip(chr(10))}\n"
                f"\thistory = {{\n{vp_txt}{bld.strip(chr(10))}\n\t\towner = {owner}\n{cores}\t}}\n"
                f"\tmanpower = {man}\n\tstate_category = {cat}\n\tbuildings_max_level_factor=1.000\n\tlocal_supplies=0.000\n}}\n")
        if sid in old:
            os.remove(old[sid])
        open(f"history/states/{sid}-Felucia - {st['name'].replace(chr(39), '')}.txt", "w", encoding="utf-8", newline="\n").write(text)
    for sid in set(old) - set(states):
        os.remove(old[sid])
    place(states, prov, pid, land, fel, fel_ids, vps[CAPITAL][-1][0], CAPITAL, rng)
    fprov = {p for st in states.values() for p in st["provinces"]}
    # names
    def fs(s):
        for sid in names:
            s = re.sub(rf'\n STATE_{sid}:\d* "[^"]*"', "", s)
        return s.rstrip("\n") + "\n" + "".join(f' STATE_{sid}:0 "{n}"\n' for sid, n in sorted(names.items()))
    rw("localisation/english/state_names_l_english.yml", fs)
    def fv(s):
        s = re.sub(r'\n VICTORY_POINTS_(\d+):\d* "[^"]*"', lambda m: "" if int(m.group(1)) in fprov else m.group(0), s)
        return s.rstrip("\n") + "\n" + "".join(f' VICTORY_POINTS_{p}:0 "{n}"\n' for p, n in vp_names.items())
    rw("localisation/english/victory_points_l_english.yml", fv)
    rw(REGION, lambda s: re.sub(r"\tweather=\{.*\n\t\}", WEATHER, s, count=1, flags=re.S))
    for sid, st in sorted(states.items()):
        print(f"{sid:5} {st['kind']:5} {len(st['provinces']):3} provinces  {st['name']}")
    country()


def place(states, prov, pid, land, fel, state_ids, port_p, capital, rng):
    """buildings.txt and unitstacks.txt for every state / province of one planet (mask `fel`), the capital's
    airport + rocket site on port_p, railways cut at the planet, supply hubs, hyperspace lanes re-anchored.
    states: sid -> dict(kind, provinces, coastal, main); prov: province -> dict(zone, coastal, sea, centre).
    state_ids: every state id of the planet, old and new (their old map positions go)."""
    import planet_terrain_gen as g
    from scipy import ndimage as ndi
    H, W = pid.shape
    fel_ids = state_ids
    # ── positions: buildings.txt and unitstacks.txt for every Felucian state / province ──
    hm = np.asarray(g.load("map/heightmap.bmp").convert("L")).astype(float)
    pos = lambda r, c: (float(c), hm[int(r), int(c)] / 10, float(H - 1 - r))
    seaish = ~land
    def centre(p):
        m = pid == p
        d = ndi.distance_transform_edt(m)
        r, c = np.unravel_index(np.argmax(d), d.shape)
        return r, c
    def coast(p):
        m = pid == p
        ring = m & ndi.binary_dilation(seaish)
        rs, cs = np.nonzero(ring if ring.any() else m)
        r0, c0 = centre(p)
        k = np.argmax((rs - r0) ** 2 + (cs - c0) ** 2)
        r, c = rs[k], cs[k]
        cy, cx = np.nonzero(fel)
        ang = math.atan2(-(r - cy.mean()), c - cx.mean())                 # facing away from the planet
        return r, c, ang
    rows = []
    for sid, st in states.items():
        provs = st["provinces"]
        land_px = np.argwhere(np.isin(pid, [p for p in provs if prov[p]["zone"] != "corridor"]))
        for b, n in STATE_BUILDINGS.items():
            for _ in range(n):
                r, c = land_px[rng.integers(len(land_px))]
                x, y, zz = pos(r, c)
                rows.append(f"{sid};{b};{x:.2f};{y:.2f};{zz:.2f};{rng.uniform(0, 6.28):.2f};0")
        if st["coastal"]:
            r, c, ang = coast(st["coastal"][0])
            x, y, zz = pos(r, c)
            rows.append(f"{sid};dockyard;{x:.2f};{y:.2f};{zz:.2f};{ang:.2f};0")
        for p in provs:
            r, c = centre(p)
            for b in PROVINCE_BUILDINGS:
                x, y, zz = pos(r + rng.uniform(-0.8, 0.8), c + rng.uniform(-0.8, 0.8))
                rows.append(f"{sid};{b};{x:.2f};{y:.2f};{zz:.2f};{rng.uniform(0, 6.28):.2f};0")
            if prov[p]["coastal"]:
                r, c, ang = coast(p)
                x, y, zz = pos(r, c)
                for b in COAST_BUILDINGS:
                    rows.append(f"{sid};{b};{x:.2f};{y:.2f};{zz:.2f};{ang:.2f};{prov[p]['sea']}")
    keep = [l for l in open("map/buildings.txt", encoding="utf-8-sig", newline="")
            if not (l.split(";")[0].isdigit() and int(l.split(";")[0]) in fel_ids)]
    end = "\r\n" if keep and keep[0].endswith("\r\n") else "\n"
    open("map/buildings.txt", "w", encoding="utf-8", newline="").write("".join(keep) + "".join(r + end for r in rows))
    # unit stacks: the same set of stack types as other provinces of the same kind, around the province centre
    us = [l for l in open("map/unitstacks.txt", encoding="utf-8-sig", newline="")]
    fprov = {p for st in states.values() for p in st["provinces"]}
    other = {}
    for l in us:
        q = l.split(";")
        if q[0].isdigit() and int(q[0]) not in fprov:
            other.setdefault(int(q[0]), []).append(q)
    types_of = lambda p: [q[1] for q in other[p]]
    coastal_ref = max(p for p in other if len(other[p]) == 21)
    inland_ref = max((p for p in other if len(other[p]) == 17), key=lambda p: p)
    out = [l for l in us if not (l.split(";")[0].isdigit() and int(l.split(";")[0]) in fprov)]
    end = "\r\n" if out and out[0].endswith("\r\n") else "\n"
    for p in sorted(fprov):
        ref = other[coastal_ref if prov[p]["coastal"] else inland_ref]
        r0, c0 = centre(p)
        for q in ref:
            t = int(q[1])
            r, c, ang = r0 + rng.uniform(-1, 1), c0 + rng.uniform(-1, 1), float(q[5])
            x, y, zz = pos(r, c)
            out.append(f"{p};{t};{x:.2f};{y:.2f};{zz:.2f};{ang:.2f};{q[6].strip()}{end}")
    open("map/unitstacks.txt", "w", encoding="utf-8", newline="").write("".join(out))
    # airport and rocket site: the capital's spaceport
    for fn in ("map/airports.txt", "map/rocketsites.txt"):
        rw(fn, lambda s: re.sub(rf"(?m)^{capital}\s*=\s*\{{[^}}]*\}}", f"{capital} = {{ {port_p} }}", s))
    # railways stop at Felucia; supply hubs at every passable state's main province
    rails = []
    for line in open("map/railways.txt"):
        q = line.split()
        if len(q) < 3:
            continue
        seg = []
        for p in map(int, q[2:]):
            if p in fprov:
                if len(seg) > 1:
                    rails.append((q[0], seg))
                seg = []
            else:
                seg.append(p)
        if len(seg) > 1:
            rails.append((q[0], seg))
    open("map/railways.txt", "w", newline="\n").write("".join(f"{lvl} {len(sg)} {' '.join(map(str, sg))} \n" for lvl, sg in rails))
    nodes = [l for l in open("map/supply_nodes.txt") if not (len(l.split()) > 1 and int(l.split()[1]) in fprov)]
    nodes += [f"1 {st['main']}\n" for st in states.values() if st["kind"] != "white"]
    open("map/supply_nodes.txt", "w", newline="\n").write("".join(nodes))
    # hyperspace lanes: re-anchor on the passable coastal province facing the other end
    def pcentre(p):
        rs, cs = np.nonzero(pid == p)
        return rs.mean(), cs.mean()
    landing = [p for p in fprov if prov[p]["coastal"] and prov[p]["zone"] not in ("white", "mountain")]   # passable
    lines = open("map/adjacencies.csv", encoding="utf-8-sig", newline="").readlines()
    for i, l in enumerate(lines):
        q = l.split(";")
        if len(q) > 3 and q[0].lstrip("-").isdigit() and q[1].lstrip("-").isdigit():
            a, b = int(q[0]), int(q[1])
            if (a in fprov) != (b in fprov):
                far = b if a in fprov else a
                fr, fc = pcentre(far)
                pick = min(landing, key=lambda p: math.hypot(prov[p]["centre"][0] - fr, prov[p]["centre"][1] - fc))
                q[0 if a in fprov else 1] = str(pick)
                lines[i] = ";".join(q)
    open("map/adjacencies.csv", "w", encoding="utf-8", newline="").write("".join(lines))


# ── the Felucian tribes: a country nobody can deal with; at peace, but raiding the Guild's frontier ──
COLOR = (178, 92, 40)            # rust orange
DESC = ("Felucia's native peoples never accepted the Commerce Guild's plantations. Deep in the karst jungle, where no "
        "army can follow, their shamans answer no envoy from beyond the sky, and when the warbands are strong they "
        "come down to burn the frontier.")
JUNGLE_WAR = dict(resistance_target=0.35, resistance_growth=0.5, resistance_damage_to_garrison=0.5, compliance_gain=-0.03,
                  local_supplies=-0.4, army_speed_factor_for_controller=-0.25, recruitable_population_factor=-0.4,
                  state_production_speed_buildings_factor=-0.4)


def felucia_states():
    return sorted(int(re.match(r"(\d+)", os.path.basename(f)).group(1)) for f in glob.glob("history/states/*Felucia*.txt"))


def write(path, text, bom=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="\n").write(text)


def gfx():
    """flag: a rust-orange giant mushroom on deep jungle teal; idea icon: the same emblem"""
    from PIL import Image, ImageDraw
    K = 8
    teal, rust, cream, dark = (24, 70, 62, 255), COLOR + (255,), (236, 214, 160, 255), (14, 34, 30, 255)

    def emblem(d, cx, cy, s):
        d.rectangle([cx - 0.09 * s, cy - 0.05 * s, cx + 0.09 * s, cy + 0.55 * s], fill=cream)               # stalk
        d.pieslice([cx - 0.6 * s, cy - 0.55 * s, cx + 0.6 * s, cy + 0.25 * s], 180, 360, fill=rust)          # cap
        for dx in (-0.3, 0.05, 0.32):
            d.ellipse([cx + (dx - 0.07) * s, cy - 0.33 * s, cx + (dx + 0.07) * s, cy - 0.19 * s], fill=cream)
        d.polygon([(cx - 0.75 * s, cy + 0.55 * s), (cx - 0.35 * s, cy + 0.2 * s), (cx - 0.15 * s, cy + 0.55 * s)], fill=dark)
        d.polygon([(cx + 0.75 * s, cy + 0.55 * s), (cx + 0.4 * s, cy + 0.15 * s), (cx + 0.15 * s, cy + 0.55 * s)], fill=dark)

    w, h = 82 * K, 52 * K
    im = Image.new("RGBA", (w, h), teal)
    d = ImageDraw.Draw(im)
    for i in range(0, w, 6 * K):                         # tribal zigzag border
        d.polygon([(i, 0), (i + 3 * K, 5 * K), (i + 6 * K, 0)], fill=rust)
        d.polygon([(i, h), (i + 3 * K, h - 5 * K), (i + 6 * K, h)], fill=rust)
    emblem(d, w / 2, h / 2 - 2 * K, 30 * K)
    for size, path in (((82, 52), f"gfx/flags/{TRIBES}.tga"), ((41, 26), f"gfx/flags/medium/{TRIBES}.tga"),
                       ((10, 7), f"gfx/flags/small/{TRIBES}.tga")):
        im.resize(size, Image.LANCZOS).save(path)
    s = 65 * K
    ic = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(ic)
    d.rounded_rectangle([3 * K, 3 * K, s - 3 * K, s - 3 * K], radius=8 * K, fill=teal, outline=rust, width=2 * K)
    emblem(d, s / 2, s / 2, 40 * K)
    ic.resize((65, 65), Image.LANCZOS).save(f"gfx/interface/ideas/HOD_felucian_tribes.tga")
    p = "interface/HOD_ideas.gfx"
    if "GFX_idea_HOD_felucian_tribes" not in open(p, encoding="utf-8-sig").read():
        rw(p, lambda s: s[:s.rstrip().rfind("}")] + '\tspriteType = {\n\t\tname = "GFX_idea_HOD_felucian_tribes"\n'
           '\t\ttexturefile = "gfx/interface/ideas/HOD_felucian_tribes.tga"\n\t}\n}\n')


def country():
    states = felucia_states()
    in_felucia = "OR = { " + " ".join(f"state = {s}" for s in states) + " }"
    rw("common/country_tags/HOD_countries.txt",
       lambda s: s if f"\n{TRIBES} =" in s else s.replace('ALD = "countries/Alderaan.txt"\n',
                                                            f'ALD = "countries/Alderaan.txt"\n{TRIBES} = "countries/Felucian Tribes.txt"\n', 1))
    rgb = " ".join(map(str, COLOR))
    rw("common/countries/colors.txt", lambda s: s if f"\n{TRIBES} = {{" in s else
       s.rstrip("\n") + f"\n{TRIBES} = {{\n\tcolor = rgb {{ {rgb} }}\n\tcolor_ui = rgb {{ {rgb} }}\n}}\n")
    write("common/countries/Felucian Tribes.txt",
          f"graphical_culture = african_gfx\ngraphical_culture_2d = african_2d\n\ncolor = rgb {{ {rgb} }}\n")
    write(f"history/countries/{TRIBES} - Felucian Tribes.txt", f"""capital = 714

oob = "HOD_{TRIBES}"

set_research_slots = 1
set_stability = 0.8
set_war_support = 1.0

recruit_character = {TRIBES}_shaman_council
recruit_character = {TRIBES}_rancor_rider

set_technology = {{
	infantry_weapons = 1
	tech_support = 1
	tech_recon = 1
	tech_engineers = 1
}}

set_popularities = {{
	akaanadocrat = 0
	unitist = 0
	corist = 0
	distributionist = 85
	corporate_consortium = 0
	trade_democrat = 0
	ruusanist = 0
	inclusivist = 0
	force_magocracy = 15
}}
set_politics = {{
	ruling_party = distributionist
	last_election = "999.1.1"
	election_frequency = 48
	elections_allowed = no
}}
add_ideas = {{
	HOD_felucian_tribes
}}
# HOD: the tribes deal with no one from beyond the sky (felucia_tribes.py)
set_rule = {{
	desc = HOD_felucian_tribes_rule
	can_create_factions = no
	can_join_factions = no
	can_send_volunteers = no
	can_puppet = no
	can_guarantee_other_ideologies = no
}}

add_equipment_to_stockpile = {{
	type = infantry_equipment
	amount = 6000
	producer = {TRIBES}
}}
""")
    write(f"common/characters/{TRIBES}.txt", f"""characters={{
	{TRIBES}_shaman_council={{
		name="Council of Shamans"
		country_leader={{
			desc="{TRIBES}_shaman_council_desc"
			ideology=symbiotist_subtype
			traits={{ }}
			id=-1
		}}
	}}
	{TRIBES}_rancor_rider={{
		name="Rancor-Rider of the Abyss"
		corps_commander={{
			traits={{ }}
			skill=3
			attack_skill=3
			defense_skill=4
			planning_skill=2
			logistics_skill=3
			legacy_id=-1
		}}
	}}
}}
""")
    write(f"common/ideas/{TRIBES}_ideas.txt", f"""ideas = {{
	country = {{
		# warbands that know every cave and fungal grove: hard to find, hard to starve, impossible to reason with
		HOD_felucian_tribes = {{
			picture = HOD_felucian_tribes
			allowed = {{ original_tag = {TRIBES} }}
			removal_cost = -1
			modifier = {{
				army_defence_factor = 0.2
				army_org_factor = 0.15
				attrition = -0.5
				supply_consumption_factor = -0.6
				no_supply_grace = 240
				conscription = 0.1
				research_speed_factor = -0.5
				production_speed_buildings_factor = -0.5
			}}
		}}
	}}
}}
""")
    write("common/dynamic_modifiers/HOD_felucia_dynamic_modifiers.txt",
          "# HOD: Felucia's endless jungle war (felucia_tribes.py)\nHOD_felucian_jungle_war = {\n"
          "\ticon = GFX_idea_HOD_felucian_tribes\n\tenable = { always = yes }\n"
          + "".join(f"\t{k} = {v}\n" for k, v in JUNGLE_WAR.items()) + "}\n")
    write("common/opinion_modifiers/HOD_felucia_opinion_modifiers.txt",
          "opinion_modifiers = {\n\t# HOD: no one from beyond the sky deals with the Felucian tribes, nor they with anyone\n"
          "\tHOD_felucian_hostility = {\n\t\tvalue = -200\n\t}\n}\n")
    write("common/on_actions/HOD_felucia_on_actions.txt", f"""# HOD: the Felucian jungle war (felucia_tribes.py)
on_actions = {{
	on_startup = {{
		effect = {{
			every_state = {{
				limit = {{ {in_felucia} }}
				add_dynamic_modifier = {{ modifier = HOD_felucian_jungle_war }}
			}}
			if = {{
				limit = {{ country_exists = {TRIBES} }}
				every_country = {{
					limit = {{ NOT = {{ tag = {TRIBES} }} }}
					add_opinion_modifier = {{ target = {TRIBES} modifier = HOD_felucian_hostility }}
					reverse_add_opinion_modifier = {{ target = {TRIBES} modifier = HOD_felucian_hostility }}
				}}
			}}
		}}
	}}
}}
""")
    bw = lambda ev: (f"on_win = hod_felucia.{ev[0]}\n\t\t\t\ton_lose = hod_felucia.{ev[1]}\n\t\t\t\t"
                     f"on_cancel = hod_felucia.{ev[1]}")
    write("events/HOD_felucia_events.txt", f"""# HOD: the Felucian tribes' border wars on the Guild's frontier (felucia_tribes.py)
add_namespace = hod_felucia

# the warbands come down from the jungle: a border war on a neighbouring lowland state, when they are strong enough
country_event = {{
	id = hod_felucia.1
	title = hod_felucia.1.t
	desc = hod_felucia.1.d
	picture = GFX_country_event_seperatists_killed
	hidden = yes

	trigger = {{
		tag = {TRIBES}
		has_war = no
		NOT = {{ has_country_flag = HOD_felucian_border_war }}
		has_army_size = {{ size > 3 }}
		any_owned_state = {{
			any_neighbor_state = {{ is_owned_by = {GUILD} impassable = no }}
		}}
	}}
	mean_time_to_happen = {{ days = 150 }}

	immediate = {{
		set_country_flag = {{ flag = HOD_felucian_border_war days = 365 }}
		random_owned_state = {{
			limit = {{ any_neighbor_state = {{ is_owned_by = {GUILD} impassable = no }} }}
			save_global_event_target_as = HOD_fel_bw_attacker
			random_neighbor_state = {{
				limit = {{ is_owned_by = {GUILD} impassable = no }}
				save_global_event_target_as = HOD_fel_bw_defender
			}}
		}}
		start_border_war = {{
			change_state_after_war = no
			combat_width = 40
			minimum_duration_in_days = 21
			attacker = {{
				state = event_target:HOD_fel_bw_attacker
				num_provinces = 3
				{bw((2, 3))}
				terrain_factor = 1.5
			}}
			defender = {{
				state = event_target:HOD_fel_bw_defender
				num_provinces = 3
				{bw((4, 5))}
			}}
		}}
		{GUILD} = {{ country_event = {{ id = hod_felucia.6 }} }}
	}}
}}

# tribes win: the frontier burns
country_event = {{
	id = hod_felucia.2
	title = hod_felucia.2.t
	desc = hod_felucia.2.d
	picture = GFX_country_event_seperatists_killed
	is_triggered_only = yes
	option = {{
		name = hod_felucia.2.a
		army_experience = 10
		add_manpower = 1000
	}}
}}
# tribes beaten back into the jungle
country_event = {{
	id = hod_felucia.3
	title = hod_felucia.3.t
	desc = hod_felucia.3.d
	picture = GFX_country_event_seperatists_killed
	is_triggered_only = yes
	option = {{
		name = hod_felucia.3.a
		add_manpower = -1500
	}}
}}
# Guild holds the frontier
country_event = {{
	id = hod_felucia.4
	title = hod_felucia.4.t
	desc = hod_felucia.4.d
	picture = GFX_country_event_seperatists_killed
	is_triggered_only = yes
	option = {{
		name = hod_felucia.4.a
		army_experience = 5
	}}
}}
# Guild loses: plantations burned
country_event = {{
	id = hod_felucia.5
	title = hod_felucia.5.t
	desc = hod_felucia.5.d
	picture = GFX_country_event_seperatists_killed
	is_triggered_only = yes
	option = {{
		name = hod_felucia.5.a
		add_manpower = -3000
		add_stability = -0.03
		event_target:HOD_fel_bw_defender = {{
			damage_building = {{ type = infrastructure damage = 1 }}
		}}
	}}
}}
# the Guild hears the drums
country_event = {{
	id = hod_felucia.6
	title = hod_felucia.6.t
	desc = hod_felucia.6.d
	picture = GFX_country_event_seperatists_killed
	is_triggered_only = yes
	option = {{
		name = hod_felucia.6.a
	}}
}}
""")
    write(f"localisation/english/HOD_{TRIBES}_l_english.yml", f"""l_english:
 # HOD: the Felucian tribes and the jungle war (felucia_tribes.py)
 {TRIBES}:0 "Felucian Tribes"
 {TRIBES}_DEF:0 "the Felucian Tribes"
 {TRIBES}_ADJ:0 "Felucian"
 {TRIBES}_shaman_council_desc:0 "{DESC}"
 HOD_felucian_tribes:0 "Children of the Fungal Jungle"
 HOD_felucian_tribes_desc:0 "{DESC}"
 HOD_felucian_tribes_rule:0 "The Felucian tribes answer no envoy from beyond the sky."
 HOD_felucian_jungle_war:0 "Felucian Jungle War"
 HOD_felucian_jungle_war_desc:0 "Native warbands strike from the karst and the fungal canopy. Patrols vanish, supply columns burn, and no outsider governs more than the ground under his boots."
 HOD_felucian_hostility:0 "Felucian Hostility"
 hod_felucia.1.t:0 "The Warbands Come Down"
 hod_felucia.1.d:0 "Drums in the karst."
 hod_felucia.2.t:0 "The Frontier Burns"
 hod_felucia.2.d:0 "Our warbands fell on the outsiders' fields in [HOD_fel_bw_defender.GetName] and melted back into the jungle before their walkers could follow. The spirits of the deep groves are pleased."
 hod_felucia.2.a:0 "Back to the jungle."
 hod_felucia.3.t:0 "Driven Back"
 hod_felucia.3.d:0 "The outsiders' guns were too many. What is left of the warbands has crawled back under the canopy to lick its wounds."
 hod_felucia.3.a:0 "The jungle remembers."
 hod_felucia.4.t:0 "The Frontier Holds"
 hod_felucia.4.d:0 "The Felucian warbands that came out of the jungle at [HOD_fel_bw_defender.GetName] have been beaten back into the karst. Our patrols will not follow them in: nothing that goes in comes out."
 hod_felucia.4.a:0 "Reinforce the clearing."
 hod_felucia.5.t:0 "Plantations Burned"
 hod_felucia.5.d:0 "Felucian warbands overran our defences at [HOD_fel_bw_defender.GetName]. The nysillin fields are ash, the walkways cut, and the attackers are gone again into jungle no army can enter."
 hod_felucia.5.a:0 "Rebuild, again."
 hod_felucia.6.t:0 "Drums in the Jungle"
 hod_felucia.6.d:0 "Felucian warbands have come out of the deep jungle and are attacking our frontier at [HOD_fel_bw_defender.GetName]. Our garrison must hold the clearing."
 hod_felucia.6.a:0 "Hold them."
""", bom=True)
    gfx()
    print(f"{TRIBES}: country files written; jungle war on states {states}")


if __name__ == "__main__":
    if sys.argv[1:] == ["country"]:
        country()
    else:
        main()
