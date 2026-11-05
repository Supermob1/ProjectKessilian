"""Hearts of Durasteel UI icons: every vanilla interface icon whose name tells what it shows is redrawn with our own
Star Wars vector pictograms (hod_vector.py) at the same size and frame count. Look = the mod's toolbar icons:
flat cyan, gold on hover / selected / "on", grey disabled; buttons keep a teal-black plate with a 1px border,
medallions become a ring badge. Vanilla art is only read for its size and silhouette, never reused.

  python -B hod_icons.py --preview OUT.png [--limit N] [--match REGEX]
  python -B hod_icons.py --write          every path goes to hod_icons_written.txt
  python -B hod_icons.py --undo
"""
import argparse, io, os, re, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
import hod_ui, hod_vector

LOG = os.path.join(os.path.dirname(__file__), "hod_icons_written.txt")
EXCL = re.compile(r"(goals/|ideas/|portrait|leader_|flag|event_pictures|loadingscreen|pdx_online|logo|topview|images/|"
                  r"counters/|anim|progress|fill|meter|gauge|glow|shine|highlight|mask|shadow|selection|terrain|weather|"
                  r"technologies/|mapicons/|bookmark|frontend|main_menu|cursor|achievement|trophies|_bg\.|background|"
                  r"overlay|line_|_line|scroll|marker|_frame|picture|medal|ribbon|profile|blueprint|equipmentdesigner/.*/|"
                  r"strip|piechart|dot\.|texticon)", re.I)

# name -> pictogram, first match wins: UI glyphs, then concepts, then unit types, then economy
RULES = [(re.compile(r, re.I), n) for r, n in [
    (r"unlock", "unlock"), (r"lock", "lock"),
    (r"close|cancel|dismiss|btn_x|exit|decline|reject|refuse|deny|(^|_)ban(_|$)|kick", "x"),
    (r"speedup|speed_up|faster", "plus"), (r"speeddown|speed_down|slower", "minus"),
    (r"menu|hamburger", "list"), (r"chat|whisper|message|(^|_)mail", "comm"), (r"(^|_)edit|rename|pencil", "wrench"),
    (r"casual", "skull"), (r"stamp", "tick"), (r"2d_3d|(^|_)3d(_|$)|camera", "eye"),
    (r"delete|trash|scrap|disband", "trash"),
    (r"speed|velocity|fast", "chevrons"),
    (r"subtract|minus|remove_one|decrease", "minus"),
    (r"(^|[_/])add|plus|new_|create|increase", "plus"),
    (r"accept|confirm|ready|_ok\b|done|complete|approv|(^|_)check(ed)?(_|$)", "tick"),
    (r"question|unknown|help|placeholder", "question"),
    (r"alert|warning|exclam|attention|urgent", "exclaim"),
    (r"play", "play"), (r"pause", "pause"), (r"stop", "stop"), (r"next|forward", "next"), (r"prev|back", "prev"),
    (r"shuffle|refresh|reorgan|rotat|convert|swap|cycle|retrain|upgrade|refit|reinforc", "refresh"),
    (r"copy|duplicate", "copy"), (r"merge|combine", "merge"), (r"split|divide", "split"),
    (r"search|filter|magnif|zoom", "search"),
    (r"list|ledger|log\b|overview", "list"),
    (r"left", "arrow_l"), (r"right", "arrow_r"), (r"(^|_)up(_|\.)|expand", "arrow_u"), (r"down|collapse", "arrow_d"),
    (r"nuke|nuclear|atomic|superweapon|wonder", "superweapon"),
    (r"radar|detect|sonar|spotting|visib", "radar"),
    (r"intel|spy|operative|agency|cryp|decrypt|infiltr|espionage|eye|privacy", "eye"),
    (r"propaganda|radio|comm(?!and)|broadcast|speech|media|music", "comm"),
    (r"medic|hospital|medical|health|wound", "medic"),
    (r"dead|death|kill|skull|casualt|attrition", "skull"),
    (r"captur|prison|pow\b|arrest|interrogat", "handcuffs"),
    (r"para|airborne|airdrop|glider", "parachute"),
    (r"mountain", "mountain"),
    (r"marine|amphib|invasion|landing|raid", "drop"),
    (r"recon|scout|binocular|observ", "binoculars"),
    (r"engineer|repair|maintenance|wrench|bridge|reliab", "wrench"),
    (r"construct|build_|_build", "construction"),
    (r"supply|logistic|crate|stockpile|materiel|lend_lease", "crate"),
    (r"fuel|oil|tibanna|petrol", "fuel"),
    (r"steel|alumin|tungsten|chromium|rubber|resource|ore\b|crystal|mineral", "crystal"),
    (r"trade|market|credit|money|econom|bank|debt|price|cost|ic\b", "credits"),
    (r"research|science|scient|(^|_)tech(_|nology|\.|$)|holocron|design", "holocron"),
    (r"jedi|force_", "jedi"), (r"sith", "sith"),
    (r"leader|monarch|king|royal|ruler|crown|emperor", "crown"),
    (r"politic|government|cabinet|parliament|senate|law|minister|advisor|election|party|ideolog", "senate"),
    (r"stability|balance|scale", "scales"),
    (r"war_support|warsupport|morale|nationalism|unrest|resistance|revolt|partisan|coup", "fist"),
    (r"manpower|population|people|recruit|conscript|volunteer|player", "people"),
    (r"dockyard|shipyard|naval_factory|naval_industry", "shipyard"),
    (r"diplom|relation|alliance|pact|guarantee|access|treaty|peace|accord|join|faction|subject|puppet|autonomy", "accord"),
    (r"night", "moon"),
    (r"efficien|growth|chart|stat\b|stats|increase|level|capacity|output|bonus", "chart"),
    (r"strength|heart|organi[sz]ation(?!_)|hp\b", "heart"),
    (r"power|energy|electric|lightning", "lightning"),
    (r"target|accura|hit_chance|aim\b|sight", "target"),
    (r"bomb(?!er)|explosiv|sabotage|demolition", "bomb"),
    (r"mine", "mine"), (r"torpedo", "torpedo"), (r"rocket|missile|launcher|jet\b", "missile"),
    (r"anti_air|antiair|aa_|flak", "antiair"),
    (r"attack|offen|assault|strike|breakthrough|damage|firepower|blitz|aggress|combat|battle|war\b", "sabers"),
    (r"defen|fort|garrison|shield|entrench|hardness|protect|guard|armor_value", "shield"),
    (r"turret", "turret"), (r"cannon|gun\b|_gun", "cannon"),
    (r"artiller|howitzer|battery", "artillery"),
    (r"engine|thrust|propul", "engine"), (r"suspension|_leg", "legs"), (r"armou?r_|plating|plate", "armor"),
    (r"submarine|stealth|sub_", "stealth"), (r"carrier", "carrier"),
    (r"battleship|cruiser|destroyer|capital_ship|naval|navy|ship|fleet|convoy|maritime|port\b|sea", "capital"),
    (r"station|orbital|airbase|air_base|base\b", "station"),
    (r"transport|train|truck|motori|mechani|railway", "transport"),
    (r"cavalry|speeder|bike|horse", "speeder"),
    (r"tank|armou?red|vehicle|walker", "walker"),
    (r"cas\b|cas_|bomber|heavy_fighter|tactical|strat", "bomber"),
    (r"interceptor", "interceptor"),
    (r"air|plane|fighter|wing|aircraft", "fighter"),
    (r"infantry|soldier|division|army|militia|troop|land\b|unit|template|clone", "trooper"),
    (r"droid|robot|automat", "droid"),
    (r"flag|banner", "banner"),
    (r"home|capital|hq|headquarter", "home"),
    (r"setting|option|config|gear|cog", "cog"),
    (r"officer|general|admiral|marshal|career|rank|trait|commander|skill|specialist|expert", "rank"),
    (r"doctrine|plan\b|plan_|strategy|battleplan|map|tactic|operation|mission|order_", "map"),
    (r"state|territor|province|occup|claim|core|region|planet|world|colony", "planet"),
    (r"elite|unique|veteran|star\b|special|quality", "star"),
    (r"factory|industr|production|mio|organization|concern|manufactur|department", "factory"),
    (r"decision", "republic"),
    (r"time|clock|day\b|date|duration", "clock"),
]]


def pick(path):
    name = path[len("gfx/interface/"):-4]
    base = name.split("/")[-1]
    for text in (base, name):                         # the file name first, the folder only as a fallback
        for rx, n in RULES:
            if rx.search(text):
                return n
    return None


def shape(px):
    """'plate' (button body), 'badge' (round medallion) or 'free' (stand-alone glyph) from the vanilla silhouette."""
    m = px[..., 3] > 127
    if m.sum() < 20:
        return "free", m
    ys, xs = np.where(m)
    bw, bh = np.ptp(xs) + 1, np.ptp(ys) + 1
    fill = m.sum() / (bw * bh)
    big = bw * bh > 0.55 * m.size
    if big and fill > 0.9:
        return "plate", m
    if big and 0.7 < fill <= 0.9 and abs(bw - bh) <= max(2, 0.12 * bw):
        return "badge", m
    return "free", m


def candidates():
    done = set(open(hod_ui.LOG).read().splitlines()) if os.path.exists(hod_ui.LOG) else set()
    mine = set(open(LOG).read().splitlines()) if os.path.exists(LOG) else set()
    for path, (frames, cornered) in sorted(hod_ui.vanilla_sprites().items()):
        if not path.startswith("gfx/interface/") or path in done or cornered or EXCL.search(path):
            continue
        if hod_ui.find(hod_ui.MOD, path) and path not in mine:
            continue                                   # the mod's own art
        subject = pick(path)
        checkbox = "checkbox" in path
        if not subject and not checkbox:
            continue
        src = hod_ui.find(hod_ui.VANILLA, path)
        if not src:
            continue
        try:
            px = np.array(Image.open(src).convert("RGBA"))
        except Exception:
            continue
        fw = px.shape[1] // max(frames, 1)
        if not (12 <= max(fw, px.shape[0]) <= 160) or min(fw, px.shape[0]) < 8 or frames > 4:
            continue                                   # strips of 5+ frames are different icons per frame
        f0 = px[:, :fw]
        m = f0[..., 3] > 127
        lum = f0[..., :3].astype(float) @ [0.299, 0.587, 0.114]
        if min(f0.shape[:2]) >= 56 and m.mean() > 0.88 and m.any() and lum[m].std() > 15 and shape(f0)[0] != "plate":
            continue                                   # a picture (map, photo), not an icon
        if frames > 1 and any((((px[:, k * fw:(k + 1) * fw, 3] > 127) & m).sum() /
                               max(((px[:, k * fw:(k + 1) * fw, 3] > 127) | m).sum(), 1)) < 0.7 for k in range(1, frames)):
            continue                                   # frames are different icons, not states of one
        yield path, px, frames, subject


COL = {0: hod_ui.CYAN, 1: hod_ui.GOLD, 2: hod_ui.GOLD, 3: hod_ui.GREY}


def frame(px, subject, state, checkbox, on):
    h, w = px.shape[:2]
    kind, m = shape(px)
    col = COL[state]
    out = np.zeros((h, w, 4), float)
    if kind == "plate":
        flat = px.copy()
        flat[..., :3] = 0                              # plain plate: no vanilla detail to trace
        out = hod_ui.draw(flat, None, state).astype(float)
        box, pad = m, 0.3
    elif kind == "badge":
        disc = ndimage.binary_erosion(m)
        out[disc, :3] = hod_ui.PLATE
        out[disc, 3] = 245
        ys, xs = np.where(m)
        r = (np.ptp(xs) + 1) / 2
        ring = Image.new("L", (w * 8, h * 8), 0)
        cx, cy = (xs.min() + xs.max() + 1) / 2 * 8, (ys.min() + ys.max() + 1) / 2 * 8
        ImageDraw.Draw(ring).ellipse([cx - r * 8 + 2, cy - r * 8 + 2, cx + r * 8 - 2, cy + r * 8 - 2], outline=255,
                                     width=max(8, int(r * 0.9)))
        cov = np.array(ring.resize((w, h), Image.LANCZOS)) / 255.0
        out[..., :3] = out[..., :3] * (1 - cov[..., None]) + col * cov[..., None]
        out[..., 3] = np.maximum(out[..., 3], cov * 255)
        box, pad = m, 0.42
    else:
        box, pad = m if m.any() else np.ones_like(m), 0.0
    if checkbox and subject is None:                   # plain checkbox: empty plate, tick when "on"
        if not on:
            return np.clip(out, 0, 255).astype(np.uint8)
        subject = "tick"
    if subject:
        ys, xs = np.where(box)
        y0, x0 = ys.min(), xs.min()
        bh, bw = np.ptp(ys) + 1, np.ptp(xs) + 1
        cov = np.zeros((h, w))
        cov[y0:y0 + bh, x0:x0 + bw] = np.array(hod_vector.render(subject, bw, bh, pad)) / 255.0
        if checkbox and subject != "tick" and on:      # unit-type checkbox "on": small tick in the corner
            t = max(6, min(h, w) // 3)
            cov[h - t - 1:h - 1, w - t - 1:w - 1] = np.maximum(cov[h - t - 1:h - 1, w - t - 1:w - 1],
                                                                np.array(hod_vector.render("tick", t, t)) / 255.0)
        out[..., :3] = out[..., :3] * (1 - cov[..., None]) + col * cov[..., None]
        out[..., 3] = np.maximum(out[..., 3], cov * 255)
    return np.clip(out, 0, 255).astype(np.uint8)


def restyle(path, px, frames, subject):
    n = max(frames, 1)
    fw = px.shape[1] // n
    checkbox = "checkbox" in path
    # 2 frames: off / on (on = gold); 3-4 frames: normal / hover / pressed / disabled
    states = list(range(n)) if n in (3, 4) else ([0, 1] if n == 2 else [0] * n)
    out = np.hstack([frame(px[:, k * fw:(k + 1) * fw], subject, states[k], checkbox, n == 2 and k == 1)
                     for k in range(n)])
    if out.shape[1] < px.shape[1]:
        out = np.hstack([out, np.zeros((px.shape[0], px.shape[1] - out.shape[1], 4), np.uint8)])
    return out


def preview(items, out, cell=96):
    cols, rw = 6, cell * 2 + 8
    sheet = Image.new("RGB", (rw * cols, (cell + 12) * ((len(items) + cols - 1) // cols)), (34, 38, 44))
    d = ImageDraw.Draw(sheet)
    for i, (path, px, frames, subject) in enumerate(items):
        x, y = (i % cols) * rw, (i // cols) * (cell + 12)
        for k, arr in enumerate((px, restyle(path, px, frames, subject))):
            im = Image.fromarray(arr)
            if max(im.size) < cell // 2:              # small icons shown 2x so the drawing can be judged
                im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
            im.thumbnail((cell, cell))
            sheet.paste(im, (x + k * cell, y + 12), im)
        d.text((x + 2, y), (subject or "box") + " " + os.path.basename(path)[-24:], fill=(255, 230, 0))
    sheet.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview"); ap.add_argument("--limit", type=int, default=0); ap.add_argument("--match")
    ap.add_argument("--write", action="store_true"); ap.add_argument("--undo", action="store_true")
    a = ap.parse_args()
    if a.undo:
        for path in open(LOG).read().splitlines():
            p = hod_ui.find(hod_ui.MOD, path)
            if p:
                os.remove(p)
        os.remove(LOG); print("undone"); return
    items = [it for it in candidates() if not a.match or re.search(a.match, it[0])]
    print(len(items), "icons", file=sys.stderr)
    if a.preview:
        preview(items[:a.limit] if a.limit else items, a.preview)
    if a.write:
        keep = {it[0] for it in items}
        for path in (open(LOG).read().splitlines() if os.path.exists(LOG) else []):
            p = hod_ui.find(hod_ui.MOD, path)
            if p and path not in keep:
                os.remove(p)                           # back to vanilla
        with open(LOG, "w") as log:
            for path, px, frames, subject in items:
                dst = os.path.join(hod_ui.MOD, path)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                buf = io.BytesIO()
                Image.fromarray(restyle(path, px, frames, subject)).save(buf, "DDS" if dst.lower().endswith(".dds") else "TGA")
                open(dst, "wb").write(buf.getvalue()); log.write(path + "\n")
        print("wrote", len(items), "->", LOG)


if __name__ == "__main__":
    main()
