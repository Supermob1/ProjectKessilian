"""The galaxy chart's regions drawn from where the planets are (the user, 2026-10-20: the zoomed-out region overlay
must put every planet in its canon region - Deep Core planets in the Deep Core, Core worlds in the Core... - and show
the regions' names faintly in an empty part of each).

    python -B "WIPGFX/plans & scripts/galaxy_regions.py" fetch     each planet's region from its Wookieepedia infobox
                                                                  (Legends first, canon when Legends has none; cached
                                                                  by research_planet.Fetcher) -> WIPGFX/Assets/galaxy_regions.json
    python -B "WIPGFX/plans & scripts/galaxy_regions.py" chart     fits the region boundaries round the planets and bakes
                                                                  the chart (fills, outlines, names) into the alpha of
                                                                  map/terrain/ice_diffuse.dds (read by pdxwater.shader);
                                                                  preview WIPGFX/Assets/galaxy_chart_preview.png

The regions are rings round the Deep Core (Deep Core, Core Worlds, Colonies, Inner Rim, Expansion Region, Mid Rim,
Outer Rim) as in the canon chart; each ring boundary is a radius per angle, started from the old ellipses of
pdxwater.shader and bent locally until every planet lies inside its own ring. Hutt Space is a blob round its planets
inside the Outer Rim; Wild Space and the Unknown Regions lie beyond the Outer Rim.
"""
import json, math, os, re, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT_JSON = os.path.join(ROOT, "WIPGFX/Assets/galaxy_regions.json")
OUT_POS = os.path.join(ROOT, "WIPGFX/Assets/galaxy_planets.json")
CHART_NPY = os.path.join(ROOT, "WIPGFX/Assets/galaxy_chart_alpha.npy")
TAU = 2 * math.pi
RINGS = ["Deep Core", "Core Worlds", "Colonies", "Inner Rim", "Expansion Region", "Mid Rim", "Outer Rim"]
OTHER = ["Hutt Space", "Wild Space", "Unknown Regions"]
# the user, 2026-10-20: these count as Hutt Space whatever their infobox says (Legends: the Hutts' territory)
HUTT = ["Toydaria", "Nimban", "Honoghr", "Teth", "Shola", "Kessel", "Oba Diah"]
ALIASES = {"Core": "Core Worlds", "Core Worlds": "Core Worlds", "Outer Rim Territories": "Outer Rim", "Outer Rim": "Outer Rim",
           "Mid Rim": "Mid Rim", "Inner Rim": "Inner Rim", "Inner Rim Territories": "Inner Rim", "Expansion Region": "Expansion Region",
           "Colonies": "Colonies", "Deep Core": "Deep Core", "Hutt Space": "Hutt Space", "Wild Space": "Wild Space",
           "Unknown Regions": "Unknown Regions", "Western Reaches": "Outer Rim", "Slice": "Mid Rim"}


def planets():
    """{planet: (x, z, radius)} in map units (x east, z north = H-1-row): one per strategic region with land, named by
    its localisation (the planet's name; state names are not planet names)"""
    import glob
    import planet_terrain_gen as g
    land, _, pid = g.load_provinces()
    loc = dict(re.findall(r'^\s*STRATEGICREGION_(\d+):\d*\s*"([^"]*)"', open(
        os.path.join(ROOT, "localisation/english/strategic_region_names_l_english.yml"), encoding="utf-8-sig").read(), re.M))
    H = land.shape[0]
    lut = np.zeros(int(pid.max()) + 1, np.int32)
    names = {}
    for f in glob.glob(os.path.join(ROOT, "map/strategicregions/*.txt")):
        t = open(f, encoding="utf-8-sig", errors="ignore").read()
        rid = re.search(r"\bid\s*=\s*(\d+)", t).group(1)
        provs = [int(q) for q in re.search(r"provinces\s*=\s*\{([^}]*)\}", t).group(1).split()]
        lut[[q for q in provs if q < len(lut)]] = int(rid)
        names[int(rid)] = loc.get(rid, rid)
    reg = np.where(land, lut[pid], 0)
    out = {}
    for rid in np.unique(reg[reg > 0]).tolist():
        ys, xs = np.nonzero(reg == rid)
        out[names[rid]] = (float(xs.mean()), float(H - 1 - ys.mean()), math.sqrt(len(ys) / math.pi))
    return out


def region_of(text):
    """the first known region named in an infobox 'region' field"""
    for m in re.finditer(r"[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)*", text):
        for k in sorted(ALIASES, key=len, reverse=True):
            if k in m.group(0):
                return ALIASES[k]
    return None


def fetch():
    import research_planet as rp
    f = rp.Fetcher(refresh=False)
    wiki = json.load(open(os.path.join(ROOT, "WIPGFX/Assets/planet_wiki.json"), encoding="utf-8"))
    ps = planets()
    old = json.load(open(OUT_JSON, encoding="utf-8")) if os.path.exists(OUT_JSON) else {}
    want = {}
    for p in ps:
        base = wiki.get(p, {}).get("query", p).split("/")[0]
        want[p] = [f"{base}/Legends", base, f"{base} (planet)/Legends", f"{base} (planet)"]
    pages = f.pages([t for ts in want.values() for t in ts])
    res = {}
    for p, ts in want.items():
        got = None
        for t in ts:
            pg = pages.get(t, {})
            if pg.get("missing") or not pg.get("text"):
                continue
            _, box = rp.infobox(pg["text"])
            reg = region_of(box.get("region", {}).get("text", ""))
            if reg:
                got = dict(region=reg, source=t, field=box["region"]["text"][:80])
                break
        if p in OTHER + RINGS:                                              # a region's own sector of planets
            got = dict(region=p, source=None, field="")
        res[p] = got or old.get(p) or dict(region=None, source=None, field="")
    json.dump(res, open(OUT_JSON, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    miss = sorted(p for p, v in res.items() if not v["region"])
    print(f"{len(res)} planets, {len(res) - len(miss)} with a region; none for: {miss}")


# ---------------------------------------------------------------- the chart
LEVEL = {r: i for i, r in enumerate(RINGS)}
LEVEL.update({"Hutt Space": 6, "Wild Space": 7, "Unknown Regions": 8})
FILLS = [1.0, 0.62, 0.44, 0.34, 0.27, 0.19, 0.12, 0.04, 0.02]   # band brightness, Deep Core outwards (as the old chart)
LABEL = {"Deep Core": "DEEP CORE", "Core Worlds": "CORE WORLDS", "Colonies": "COLONIES", "Inner Rim": "INNER RIM",
         "Expansion Region": "EXPANSION REGION", "Mid Rim": "MID RIM", "Outer Rim": "OUTER RIM TERRITORIES",
         "Hutt Space": "HUTT SPACE", "Wild Space": "WILD SPACE", "Unknown Regions": "UNKNOWN REGIONS"}
BLEND = 200.0          # map units: how far a planet pulls the regions toward its own
PRIOR_W = 0.12         # weight of the ring layout against the planets
SMOOTH = 60.0          # map units: smoothing of the blended field before the planets' plateaus
FALL = 60.0            # map units over which a planet's own plateau fades
MARGIN = 28.0          # map units of its own region kept round every planet's disc
FONT = "C:/Windows/Fonts/ERASLGHT.TTF"
NEIGHBOURS = 6        # nearest planets that decide whether a planet sits in its own region's territory
DEEP_HEART = 130.0     # map units: radius of the Deep Core's own zone round its planets' centre (less if a Core world is near)
LABEL_SIZE = {"Deep Core": 14, "Core Worlds": 16, "Colonies": 18, "Inner Rim": 20, "Expansion Region": 22, "Mid Rim": 26,
              "Outer Rim": 30, "Hutt Space": 18, "Wild Space": 24, "Unknown Regions": 24}   # texels (2 map units)


def level_field(ps, reg, X, Z, plateau=True):
    """a smooth 'region level' over the map. Away from planets: the canon ring layout, a radial prior from the Deep
    Core (breakpoints from the planets' median distance per ring; beyond the rims Wild Space, the Unknown Regions
    west). Near planets: a weighted blend of the nearby planets' levels (BLEND map units), smoothed over SMOOTH, so the
    rings follow where the planets are. With plateau: each planet's disc + MARGIN is flattened to its own level (fading
    over FALL) so no border cuts a planet. Hutt Space is a blob field of its own. Returns (level, hutt, misfits, core)."""
    from scipy import ndimage as ndi
    core = np.mean([ps[p][:2] for p in ps if reg[p] == "Deep Core"], 0)
    dist = {p: math.hypot(ps[p][0] - core[0], ps[p][1] - core[1]) for p in ps}
    med = [float(np.median([dist[p] for p in ps if LEVEL[reg[p]] == k] or [0])) for k in range(9)]
    for k in range(1, 9):                                                    # keep the prior increasing
        med[k] = max(med[k], med[k - 1] + 60.0)
    D = np.hypot(X - core[0], Z - core[1])
    prior = np.minimum(np.interp(D, np.array(med), np.arange(9, dtype=float)), 7.0)   # beyond the rims: Wild Space
    prior = prior + 2.0 * np.clip((core[0] - 350.0 - X) / 400.0, 0, 1) * (prior > 6.5)   # the Unknown Regions lie west
    names = [p for p in ps if reg[p] != "Hutt Space"]
    num, den = PRIOR_W * prior, np.full_like(X, PRIOR_W)
    for p in names:
        x, z, r = ps[p]
        k = np.exp(-((X - x) ** 2 + (Z - z) ** 2) / (2 * BLEND ** 2))
        num += k * LEVEL[reg[p]]
        den += k
    L = ndi.gaussian_filter(num / den, SMOOTH / float(X[0, 1] - X[0, 0]))    # broad, calm boundaries
    if not plateau:
        return np.clip(L, 0, 8.4), None, [], core
    best, lvl = np.zeros_like(X), np.zeros_like(X)
    for p in names:
        x, z, r = ps[p]
        d = np.hypot(X - x, Z - z)
        b = np.clip((r + MARGIN + FALL - d) / FALL, 0, 1)
        b = b * b * (3 - 2 * b)
        take = b > best
        best, lvl = np.where(take, b, best), np.where(take, LEVEL[reg[p]], lvl)
    L = L * (1 - best) + lvl * best
    for p in names:                                                          # a planet's own disc is its region
        x, z, r = ps[p]
        L = np.where(np.hypot(X - x, Z - z) < r + 6.0, float(LEVEL[reg[p]]), L)
    bad = [p for p in names if np.any(np.floor(L[np.hypot(X - ps[p][0], Z - ps[p][1]) < ps[p][2]] + 0.5) != LEVEL[reg[p]])]
    hutt = np.zeros_like(X)
    for p in ps:
        if reg[p] == "Hutt Space":
            x, z, r = ps[p]
            hutt = np.maximum(hutt, np.exp(-((X - x) ** 2 + (Z - z) ** 2) / (2 * (r + 90.0) ** 2)))
    return np.clip(L, 0, 8.4), hutt, bad, core


def chart():
    """fits the regions, bakes the chart into the alpha of map/terrain/ice_diffuse.dds, writes a preview"""
    from PIL import Image, ImageDraw, ImageFont
    from scipy import ndimage as ndi
    import planet_terrain_gen as g
    ps = planets()
    json.dump(ps, open(OUT_POS, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    data = json.load(open(OUT_JSON, encoding="utf-8"))
    reg = {p: "Hutt Space" if p in HUTT else v["region"] for p, v in data.items()}
    ps = {p: v for p, v in ps.items() if reg.get(p)}
    land, _, _ = g.load_provinces()
    H, W = land.shape
    h, w = H // 2, W // 2                                                   # ice_diffuse.dds is half the map
    rows, cols = np.mgrid[:h, :w].astype(np.float32)
    X, Z = cols * 2 + 1, (H - 1) - (rows * 2 + 1)
    deep = [ps[p] for p in ps if reg[p] == "Deep Core"]                     # the Deep Core's heart (canon chart: a
    others = [math.hypot(ps[p][0] - np.mean([d[0] for d in deep]), ps[p][1] - np.mean([d[1] for d in deep])) - ps[p][2]
              for p in ps if reg[p] != "Deep Core"]                         # bright core round the galactic centre)
    fit = dict(ps, **{"_heart": (float(np.mean([d[0] for d in deep])), float(np.mean([d[1] for d in deep])),
                                 max(40.0, min(DEEP_HEART, min(others) - MARGIN)))})
    # the user, 2026-10-20: no pockets round odd planets - a planet none of whose NEIGHBOURS nearest planets share its
    # region sits in another region's territory: it is shown in its neighbours' (distance-weighted) majority region.
    # Repeated until nothing changes; the Deep Core and Hutt Space keep theirs.
    shown = dict(reg)
    names_ = [p for p in ps]
    P = np.array([ps[p][:2] for p in names_])
    dcx, dcz = np.mean([ps[q][0] for q in ps if reg[q] == "Deep Core"]), np.mean([ps[q][1] for q in ps if reg[q] == "Deep Core"])
    rad = {q: math.hypot(ps[q][0] - dcx, ps[q][1] - dcz) for q in ps}
    med = [float(np.median([rad[q] for q in ps if LEVEL[reg[q]] == k] or [0])) for k in range(7)]
    for k in range(1, 7):
        med[k] = max(med[k], med[k - 1] + 60.0)
    radial = lambda q: int(np.clip(round(float(np.interp(rad[q], med, np.arange(7)))), 1, 6))   # its ring by distance
    for _once in (1,):                                                       # one pass on the canon labels: no cascades
        for a, p in enumerate(names_):
            if shown[p] in ("Deep Core", "Hutt Space") or p in OTHER + RINGS:  # (a sector named after its region)
                continue
            d = np.hypot(*(P - P[a]).T)
            nn = [names_[b] for b in np.argsort(d)[1:NEIGHBOURS + 1]]
            same = sum(reg[q] == reg[p] or {reg[q], reg[p]} == {"Wild Space", "Unknown Regions"} for q in nn)
            top = max(sum(reg[q] == r_ for q in nn) for r_ in {reg[q] for q in nn})
            if same >= 2 or top < 3 or top <= same:                          # it belongs where it is
                continue
            votes = {}
            for q in nn:
                rq = "Outer Rim" if reg[q] == "Hutt Space" else reg[q]
                votes[rq] = votes.get(rq, 0.0) + 1.0 / max(d[names_.index(q)], 1.0)
            votes.pop("Deep Core", None)                                      # nothing joins the Deep Core
            if not votes:
                continue
            shown[p] = max(votes, key=votes.get)
            if shown[p] in RINGS and abs(LEVEL[shown[p]] - radial(p)) > 1:      # no finger reaching across the rings
                shown[p] = RINGS[radial(p)]
    # then the planets the rings run past: where the smooth field (no plateaus) round a planet reads more than 3/4 of a
    # ring away from its region, it would sit in a bump - it joins the ring it lies in (field recomputed each round)
    Xc, Zc = X[::4, ::4], Z[::4, ::4]
    for _round in range(3):
        Lc, _h, _b, _c = level_field(fit, dict(shown, _heart="Deep Core"), Xc, Zc, plateau=False)
        moved = 0
        for p, (x, z, r) in ps.items():
            if shown[p] in ("Deep Core", "Core Worlds", "Hutt Space", "Unknown Regions") or p in OTHER + RINGS:
                continue
            v = float(Lc[int(np.clip(round(((H - 1 - z) - 1) / 8), 0, Lc.shape[0] - 1)), int(np.clip(round((x - 1) / 8), 0, Lc.shape[1] - 1))])
            if abs(v - LEVEL[shown[p]]) > 0.75:
                lv = int(np.clip(round(v), 1, 7))
                new = RINGS[lv] if lv < 7 else "Wild Space"
                if new != shown[p]:
                    shown[p] = new
                    moved += 1
        if not moved:
            break
    for p in data:
        data[p]["chart_region"] = shown.get(p, data[p]["region"])
    json.dump(data, open(OUT_JSON, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    changed = {p: f"{reg[p]} -> {shown[p]}" for p in ps if shown[p] != reg[p]}
    reg = shown
    L, hutt, bad, core = level_field(fit, dict(reg, _heart="Deep Core"), X, Z)
    lev = np.clip(np.floor(L + 0.5), 0, 8).astype(int)
    hm = (hutt > 0.5) & (lev >= 5) & (lev <= 7)
    yy, xx = np.mgrid[-45:46, -45:46]                                       # one territory, not islands round its worlds
    hm = ndi.binary_fill_holes(ndi.binary_closing(np.pad(hm, 45), xx ** 2 + yy ** 2 <= 45 ** 2))[45:-45, 45:-45] & (lev >= 5) & (lev <= 7)
    for p, (x, z, r) in ps.items():                                         # no other region's planet swallowed
        if reg[p] != "Hutt Space":
            hm &= np.hypot(X - x, Z - z) > r + MARGIN
    region = np.where(hm, 9, lev)                                           # 9 = Hutt Space
    fills = np.array(FILLS)                                                 # brighter toward the core, as the old chart
    k0 = np.clip(np.floor(L), 0, 7).astype(int)
    fill = fills[k0] + (fills[np.minimum(k0 + 1, 8)] - fills[k0]) * (L - k0)
    fill = np.where(hm, np.maximum(fill, 0.1), fill)
    edge = np.zeros((h, w), bool)                                           # outlines where the region changes
    edge[:-1] |= region[:-1] != region[1:]
    edge[:, :-1] |= region[:, :-1] != region[:, 1:]
    edge &= ~((region >= 7) & (region <= 8) & (np.roll(region, -1, 0) >= 7) & (np.roll(region, -1, 0) <= 8)
              & (np.roll(region, -1, 1) >= 7) & (np.roll(region, -1, 1) <= 8))   # no line between Wild and Unknown
    line = np.clip(ndi.gaussian_filter(edge.astype(np.float32), 0.8) * 2.2, 0, 1)
    near = np.zeros((h, w), bool)                                           # labels keep clear of the planets
    touch = np.zeros((h, w), bool)                                          # (and never run under one)
    for p, (x, z, r) in ps.items():
        d = np.hypot(X - x, Z - z)
        near |= d < r + 70.0
        touch |= d < r + 14.0
    text = Image.new("L", (w, h), 0)
    dr = ImageDraw.Draw(text)
    placed = {}
    names = {i: n for n, i in LEVEL.items() if n != "Hutt Space"}
    names[9] = "Hutt Space"
    taken = np.zeros((h, w), bool)                                          # labels already placed (+ a gap)
    edgeband = ndi.binary_dilation(edge, iterations=6)
    for i, n in names.items():
        own = region == i
        if not own.any():
            continue
        ys, xs = np.nonzero(own)
        ay, ax = ys.mean(), xs.mean()                                       # aim: the middle of the region
        allowed = own & ~edgeband & ~taken
        allowed[:30], allowed[-30:], allowed[:, :30], allowed[:, -30:] = False, False, False, False
        if n == "Wild Space":                                               # away from the Unknown Regions (west)
            allowed[:, : w // 2] = False
            ay, ax = h * 0.5, w * 0.85
        words = LABEL[n].split(" ")
        layouts = [[" ".join(LABEL[n])]] + ([[" ".join(" ".join(words[:len(words) // 2 or 1])), " ".join(" ".join(words[len(words) // 2 or 1:]))]]
                                            if len(words) > 1 else [])          # letter-spaced, one line or two
        done = False
        for size in range(LABEL_SIZE[n], 9, -1):
          font = ImageFont.truetype(FONT, size)
          for lines_ in layouts:
            tw, th = int(max(font.getlength(t) for t in lines_)) + 4, size * len(lines_) + 4 * len(lines_)
            for clear in (allowed & ~near, allowed & ~touch, own & ~touch & ~taken):   # well off the planets if it can be
                fits = ndi.minimum_filter(clear, size=(th, tw), mode="constant", cval=False)
                if fits.any():
                    fy, fx = np.nonzero(fits)
                    k = int(np.argmin(np.hypot(fy - ay, fx - ax)))
                    r_, c_ = int(fy[k]), int(fx[k])
                    for li, t in enumerate(lines_):
                        lw = font.getlength(t)
                        dr.text((c_ - lw / 2, r_ - th / 2 + 2 + li * (size + 4)), t, fill=255, font=font)
                    taken[max(0, r_ - th):r_ + th, max(0, c_ - tw // 2 - th):c_ + tw // 2 + th] = True
                    placed[n] = (int(c_ * 2), int(H - 1 - r_ * 2), size)
                    done = True
                    break
            if done:
                break
          if done:
              break
    txt = np.asarray(text, np.float32) / 255
    a = np.clip(fill * 0.6 + line * 0.35 + txt * 0.42, 0, 1)
    inject(os.path.join(ROOT, "map/terrain/ice_diffuse.dds"), a)
    prev = np.stack([a * 0.45, a * 0.66, a * 0.78], -1)
    im = Image.fromarray((np.clip(prev * 1.6, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    for p, (x, z, r) in ps.items():
        cc, rr = x / 2, (H - 1 - z) / 2
        d.ellipse([cc - r / 2, rr - r / 2, cc + r / 2, rr + r / 2], outline=(255, 210, 120))
    im.save(os.path.join(ROOT, "WIPGFX/Assets/galaxy_chart_preview.png"))
    print(f"regions fitted round {len(ps)} planets; misfits {bad}; shown in another region than canon ({len(changed)}): {changed}")


def inject(path, a):
    """the chart (h x w, 0..1) into the alpha bytes of an uncompressed A8R8G8B8 DDS (rows top-down); called again by
    planet_terrain_gen.py after it copies the atmospheres into ice_diffuse.dds"""
    import struct
    raw = bytearray(open(path, "rb").read())
    hh, ww = struct.unpack("<II", raw[12:20])
    assert (hh, ww) == a.shape, ((hh, ww), a.shape)
    px = np.frombuffer(bytes(raw[128:128 + hh * ww * 4]), np.uint8).reshape(hh, ww, 4).copy()
    px[..., 3] = np.rint(a * 255).astype(np.uint8)
    raw[128:128 + px.nbytes] = px.tobytes()
    open(path, "wb").write(raw)
    np.save(CHART_NPY, np.rint(a * 255).astype(np.uint8))


def reinject():
    """after ice_diffuse.dds was rewritten from the atmospheres: the saved chart back into its alpha"""
    if os.path.exists(CHART_NPY):
        inject(os.path.join(ROOT, "map/terrain/ice_diffuse.dds"), np.load(CHART_NPY) / 255.0)


if __name__ == "__main__":
    {"fetch": fetch, "chart": chart, "reinject": reinject}[sys.argv[1]]()
