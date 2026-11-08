"""Rebuild every starting division template on the Executor mod's templates (history/units of workshop 3734223606).

    python -B "plans & scripts/sw_tree/executor_oob.py"

Run from the mod root, AFTER faction_templates.py / game_mode_history.py (they still write the old vanilla-unit
templates). Each template keeps its name, names group, is_locked and model override, and every division keeps its
place; only the battalions change, by what the old template was:
  heavy walkers/tanks  -> Executor "Heavy Vehicle Battalion": 2 heavy_vehicle + 4 blaster_infantry
  medium tanks/walkers -> "Assault Division": 3 assault_vehicle + 3 blaster_infantry
  light tanks/walkers  -> "Mobile Division":  4 light_vehicle + 2 blaster_infantry
  infantry             -> garrison / <= 2 battalions: 2 blaster_infantry ("Blaster Squadron")
                          <= 6: 4 blaster_infantry ("Imperial Regiment"), more: 9 ("Army Division", 3 x 3)
No support companies: the Executor support companies need the 977 support techs (their own REP army had none).
Also writes the 5 unlock_* OOBs the vehicle techs load (Executor's, Clone Wars names, no support).
"""
import glob, os, re, sys

LIGHT = {"light_armor", "walkers_light", "spider_droid"}
ASSAULT = {"medium_armor", "walkers_medium", "repulsor_tank_company", "medium_tank_destroyer_support"}
HEAVY = {"heavy_armor", "walkers_heavy", "walkers_modern", "super_heavy_armor"}
SKIP = re.compile(r"(_naval|HOD_air|HOD_unlock_|test_space)", re.I)
# the Executor units themselves too, so a rerun on converted files keeps each division's kind
LIGHT |= {"light_vehicle", "speeder"}
ASSAULT |= {"assault_vehicle", "armored_troop_transport"}
HEAVY |= {"heavy_vehicle", "super_heavy_vehicle"}


def regs(cols):
    """cols: [[(unit, n), ...], ...] -> regiment lines"""
    out = []
    for x, col in enumerate(cols):
        y = 0
        for unit, n in col:
            for _ in range(n):
                out.append(f"\t\t{unit} = {{ x = {x} y = {y} }}")
                y += 1
    return out


B = "blaster_infantry"
def executor_regiments(units, locked):
    if units & HEAVY:
        return "heavy", regs([[(B, 4)], [("heavy_vehicle", 2)]])
    if units & ASSAULT:
        return "assault", regs([[(B, 3)], [("assault_vehicle", 3)]])
    if units & LIGHT:
        return "light", regs([[(B, 2)], [("light_vehicle", 4)]])
    return "infantry", None


def block_end(s, i):
    i, d = s.index("{", i) + 1, 1
    while d:
        d += {"{": 1, "}": -1}.get(s[i], 0)
        i += 1
    return i


def convert(s, tag):
    out, pos, n = [], 0, 0
    for m in re.finditer(r"division_template\s*=\s*\{", s):
        if m.start() < pos:
            continue
        end = block_end(s, m.start())
        body = re.sub(r"#[^\n]*", "", s[m.end():end - 1])
        name = re.search(r'name\s*=\s*"([^"]*)"', body).group(1)
        r = re.search(r"\bregiments\s*=\s*\{", body)
        units_list = re.findall(r"(\w+)\s*=\s*\{\s*x", body[r.end():block_end(body, r.start())]) if r else []
        locked = bool(re.search(r"is_locked\s*=\s*yes", body))
        kind, lines = executor_regiments(set(units_list), locked)
        if kind == "infantry":
            k = len(units_list)
            lines = regs([[(B, 2)]] if locked or k <= 2 else [[(B, 4)]] if k <= 6 else [[(B, 3)]] * 3)
        keep = [f'\tname = "{name}"']
        # no override_model: it would freeze the division's look; the model follows the equipment (unit_models_sw.py)
        for key in ("division_names_group", "is_locked", "template_counter"):
            mm = re.search(r"\b%s\s*=\s*(\S+)" % key, body)
            if mm:
                keep.append(f"\t{key} = {mm.group(1)}")
        new = "division_template = {\n" + "\n".join(keep) + "\n\tregiments = {\n" + "\n".join(lines) + "\n\t}\n}"
        out.append(s[pos:m.start()] + new)
        pos, n = end, n + 1
    return "".join(out) + s[pos:], n


UNLOCKS = {   # Executor history/units/unlock_*.txt, Clone Wars names
    "unlock_light": ("Walker Mobile Division", [[(B, 2)], [("light_vehicle", 4)]]),
    "unlock_assault": ("Repulsor Assault Division", [[(B, 3)], [("assault_vehicle", 3)]]),
    "unlock_heavy": ("Heavy Walker Battalion", [[(B, 4)], [("heavy_vehicle", 2)]]),
    "unlock_speeder": ("Speeder Division", [[("speeder", 2)], [("speeder", 2)]]),
    "unlock_troop_transport": ("Armoured Transport Division", [[("armored_troop_transport", 2)], [("armored_troop_transport", 2)]]),
}


def self_check():
    t, n = convert('division_template = {\n\tname = "X"\n\tis_locked = yes\n\tregiments = {\n\t\tinfantry = { x = 0 y = 0 }\n'
                   '\t}\n\tsupport = { recon = { x = 0 y = 0 } }\n}\nunits = { }\n', "REP")
    assert n == 1 and t.count("blaster_infantry") == 2 and "recon" not in t and "units = { }" in t, t
    t, _ = convert('division_template = {\n\tname = "W"\n\toverride_model = REP_old_trooper_entity\n\tregiments = {\n'
                   '\t\twalkers_light = { x = 0 y = 0 }\n\t\tinfantry = { x = 1 y = 0 }\n\t}\n}\n', "REP")
    assert "override_model" not in t and t.count("light_vehicle") == 4, t
    t2, _ = convert(t, "REP")                      # a rerun must not change a converted template
    assert t2 == t, t2


def write_ai():
    def role(key, role_, entries, prio):
        out = [f"{key} = {{", f"\trole = {role_}", f"\tupgrade_prio = {{ base = {prio} }}"]
        for k, rg in entries.items():
            out.append(f"\t{k} = {{\n\t\tupgrade_prio = {{ base = 1 }}\n\t\ttarget_template = {{\n\t\t\tregiments = {{\n"
                       + "".join(f"\t\t\t\t{u} = {n}\n" for u, n in rg.items()) + "\t\t\t}\n\t\t}\n\t\ttarget_min_match = 0.6\n\t}")
        return "\n".join(out + ["}"])
    txt = "\n\n".join([
        role("hod_sw_infantry", "infantry", {"hod_sw_army_division": {B: 9}}, 3),
        role("hod_sw_armour", "armor", {"hod_sw_assault_division": {B: 3, "assault_vehicle": 3},
                                         "hod_sw_heavy_battalion": {B: 4, "heavy_vehicle": 2}}, 2),
        role("hod_sw_mobile", "mobile", {"hod_sw_walker_mobile": {B: 2, "light_vehicle": 4}}, 1),
        role("hod_sw_garrison", "garrison", {"hod_sw_garrison": {B: 2}}, 1)])
    open("common/ai_templates/HOD_faction_templates.txt", "w", encoding="utf-8", newline="\n").write(
        "# HOD: AI division targets on the Executor tree's units, for every country (sw_tree/executor_oob.py)\n\n" + txt + "\n")


if __name__ == "__main__":
    self_check()
    write_ai()
    total = 0
    for f in glob.glob("history/units/*.txt"):
        if SKIP.search(os.path.basename(f)):
            continue
        raw = open(f, "rb").read()
        if "--from-head" in sys.argv:    # rebuild from the committed (pre-Executor) templates; placements must match
            import subprocess
            head = subprocess.run(["git", "show", "HEAD:" + f.replace("\\", "/")], capture_output=True)
            if head.returncode == 0:
                units_of = lambda b: re.sub(r"\s+", " ", b.decode("utf-8-sig")[b.decode("utf-8-sig").find("\nunits"):])
                assert units_of(head.stdout) == units_of(raw.replace(b"\r\n", b"\n")) or b"\nunits" not in raw, f
                raw = head.stdout.replace(b"\r\n", b"\n")
        bom = raw.startswith(b"\xef\xbb\xbf")
        s = raw.decode("utf-8-sig").replace("\r\n", "\n")
        tag = (re.match(r"HOD_([A-Za-z]{3})\.txt$", os.path.basename(f)) or [None, ""])[1].upper()
        s2, n = convert(s, tag)
        if n:
            c = re.sub(r"#[^\n]*", "", s2)
            assert c.count("{") == c.count("}"), f
            open(f, "wb").write((b"\xef\xbb\xbf" if bom else b"") + s2.encode("utf-8"))
            total += n
    for oob, (name, cols) in UNLOCKS.items():
        open(f"history/units/{oob}.txt", "w", encoding="utf-8-sig", newline="\n").write(
            f"# HOD: Executor template, Clone Wars name (plans & scripts/sw_tree/executor_oob.py)\ndivision_template = {{\n"
            f'\tname = "{name}"\n\tregiments = {{\n' + "\n".join(regs(cols)) + "\n\t}\n}\n")
    left = {u for f in glob.glob("history/units/*.txt") if not SKIP.search(f)
            for u in re.findall(r"(\w+)\s*=\s*\{\s*x\s*=", open(f, encoding="utf-8-sig").read())}
    print("templates rebuilt:", total, "| subunits now used:", sorted(left))
