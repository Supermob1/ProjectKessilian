"""Bring HoD's copies of vanilla military files up to the installed vanilla version, keeping HoD's own edits.

    python "WIPGFX/plans & scripts/vanilla_sync.py"          dry run: report what would change
    python "WIPGFX/plans & scripts/vanilla_sync.py" apply    rewrite the files

Run from the mod root. Per top-level block (tech, unit, equipment, module), vanilla vs mod differences are decided by
the mod's git history:
  - the vanilla side was in some past version of the mod file  -> HoD changed or removed it on purpose: keep the mod
  - the vanilla side never was in the mod                        -> new vanilla content: take it (years -> HoD calendar)
  - anything naming vanilla countries/focuses, AI weights, tech positions and start years -> keep the mod
Blocks only vanilla has are added unless they are locked to a vanilla country; blocks only the mod has are kept.
"""
import difflib, glob, os, re, subprocess, sys

V = "F:/SteamLibrary/steamapps/common/Hearts of Iron IV"
DIRS = ["common/technologies", "common/units", "common/units/equipment", "common/units/equipment/modules",
        "common/units/equipment/upgrades", "common/units/critical_parts"]
HOD_FILES = {"republic_military.txt", "cis_droid_military.txt", "special_forces_doctrine.txt"}
TAGGY = re.compile(r"\b(original_tag|tag|TAG|has_war_with|has_War_with|has_completed_focus|is_ai|has_government|"
                   r"is_in_faction_with|has_idea|has_country_flag|controls_state|is_historical_focus_on|"
                   r"[A-Z]{3}(_\w+)?\s*=\s*(\{|yes)|\w+_(effect|focus)\b|mio:[A-Z]{3}|GFX_[A-Z]{3}_)")
KEEP_MOD_KEYS = ("ai_will_do", "folder", "start_year")   # techs: HoD's AI weights, layout and calendar


def block_end(s, i):
    d = 1
    while d and i < len(s):
        d += {"{": 1, "}": -1}.get(s[i], 0)
        i += 1
    return i


def blocks(s):
    out = {}
    for m in re.finditer(r"^\t(\w+)\s*=\s*\{", s, re.M):
        out.setdefault(m.group(1), (m.start(), block_end(s, m.end())))
    return out


def norm(line):
    l = re.sub(r"#.*", "", line).strip()
    l = re.sub(r"@?\b(1[89]\d\d|9[5-9]\d)\b", "Y", l)
    return re.sub(r"\s+", " ", l).replace('"', "")


def to_hod_years(line, at_map):
    line = re.sub(r"@(1[89]\d\d)\b", lambda m: at_map.get(m.group(0), m.group(0)), line)
    return re.sub(r"\b(1[89]\d\d)(?=\D|$)", lambda m: str(max(960, int(m.group(1)) - 960)), line)


def at_vars(vtext, mtext):
    """@1936 -> @976 by matching the variables' values in the two file headers"""
    vv = dict((v, k) for k, v in re.findall(r"(@\d+)\s*=\s*(-?\d+)", vtext))
    mv = dict((v, k) for k, v in re.findall(r"(@\d+)\s*=\s*(-?\d+)", mtext))
    return {vv[x]: mv[x] for x in vv if x in mv}


def history(path):
    """every normalized line any committed version of the mod file ever had"""
    seen = set()
    revs = subprocess.run(["git", "log", "--format=%H", "--", path], capture_output=True, text=True).stdout.split()
    for r in revs:
        for rev in (r, r + "^"):
            t = subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True).stdout.decode("utf-8-sig", "ignore")
            seen.update(norm(l) for l in t.split("\n"))
    return seen


REVERT = ("4742d49e", "ccc4e841")   # tech files were deleted and restored: blame through the restore
HAND_MAX = 30                        # a commit adding at most this many lines to a file is a hand edit, not a vanilla copy


def blame_commits(path, rev="HEAD"):
    out = subprocess.run(["git", "blame", "--porcelain", rev, "--", path], capture_output=True, text=True,
                         encoding="utf-8", errors="ignore").stdout
    return [m.group(1)[:8] for m in re.finditer(r"^([0-9a-f]{40}) \d+ \d+", out, re.M)]


def hand_lines(path):
    """normalized lines of the mod file that come from small hand-edit commits"""
    added = {}
    log = subprocess.run(["git", "log", "--format=@%h", "--numstat", "--", path], capture_output=True, text=True).stdout
    c = None
    for l in log.split("\n"):
        if l.startswith("@"):
            c = l[1:9]
        elif l.strip() and c:
            a = l.split("\t")[0]
            added[c] = int(a) if a.isdigit() else 0
    text = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True).stdout.decode("utf-8-sig", "ignore").split("\n")
    commits = blame_commits(path)
    if REVERT[0] in commits:
        old = blame_commits(path, REVERT[1] + "^")
        commits = [old[i] if c == REVERT[0] and i < len(old) else c for i, c in enumerate(commits)]
        log = subprocess.run(["git", "log", "--format=@%h", "--numstat", REVERT[1] + "^", "--", path], capture_output=True, text=True).stdout
        for l in log.split("\n"):
            if l.startswith("@"):
                c = l[1:9]
            elif l.strip() and c:
                a = l.split("\t")[0]
                added.setdefault(c, int(a) if a.isdigit() else 0)
    return {norm(t) for t, c in zip(text, commits) if added.get(c, 999) <= HAND_MAX and norm(t)}


def sub_block(text, key):
    m = re.search(r"\n(\t+)%s\s*=\s*" % key, text)
    if not m:
        return None
    j = m.end()
    if text[j] == "{":
        return m.start(), block_end(text, j + 1)
    e = text.find("\n", j)
    return m.start(), e if e >= 0 else len(text)


def merge_block(vb, mb, hist, hand, at_map, is_tech):
    if is_tech:      # HoD's AI weights, folder position and start year replace vanilla's
        for k in KEEP_MOD_KEYS:
            ms, vs = sub_block(mb, k), sub_block(vb, k)
            if ms and vs:
                vb = vb[:vs[0]] + mb[ms[0]:ms[1]] + vb[vs[1]:]
    vl, ml = vb.split("\n"), mb.split("\n")
    vk, mk = [norm(x) for x in vl], [norm(x) for x in ml]
    out, took = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, vk, mk, autojunk=False).get_opcodes():
        if op == "equal":
            out += ml[j1:j2]
            continue
        vside = [x for x in vk[i1:i2] if x]
        mside = [x for x in mk[j1:j2] if x]
        if (not vside or all(x in hist for x in vside) or any(TAGGY.search(x) for x in vside)
                or any(x in hand for x in mside)):
            out += ml[j1:j2]                       # HoD's version
        else:
            new = [to_hod_years(x, at_map) for x in vl[i1:i2]]
            out += new                             # new vanilla content
            took.append(([x for x in mk[j1:j2] if x], vside))
    return "\n".join(out), took


def country_locked(b):
    a = sub_block(b, "allow")
    return bool(a and TAGGY.search(b[a[0]:a[1]])) or bool(re.match(r"\t[A-Z]{3}_", b))


def sync_file(path, apply):
    vp = f"{V}/{path}"
    raw = open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    m = raw.decode("utf-8-sig", errors="ignore")
    crlf = "\r\n" in m
    m = m.replace("\r\n", "\n")
    v = open(vp, encoding="utf-8-sig", errors="ignore").read().replace("\r\n", "\n")
    mb, vb = blocks(m), blocks(v)
    hist, hand, at_map, is_tech = history(path), hand_lines(path), at_vars(v, m), path.startswith("common/technologies")
    report, edits = [], []
    for name, (vs, ve) in vb.items():
        if name in mb:
            ms, me = mb[name]
            merged, took = merge_block(v[vs:ve], m[ms:me], hist, hand, at_map, is_tech)
            if took:
                edits.append((ms, me, merged))
                for old, new in took:
                    report.append(f"  {name}: " + (" | ".join(old) or "(nothing)") + "  ->  " + " | ".join(new))
        elif not country_locked(v[vs:ve]):
            text = "\n".join(to_hod_years(x, at_map) for x in v[vs:ve].split("\n"))
            edits.append((None, None, text))
            report.append(f"  + new block {name}")
    if apply and edits:
        new_blocks = [t for s, e, t in edits if s is None]
        for s, e, t in sorted([x for x in edits if x[0] is not None], reverse=True):
            m = m[:s] + t + m[e:]
        if new_blocks:
            end = m.rstrip().rfind("}")
            m = m[:end] + "\t# HOD vanilla_sync: added from vanilla\n" + "\n".join(new_blocks) + "\n" + m[end:]
        out = m.replace("\n", "\r\n") if crlf else m
        open(path, "wb").write((b"\xef\xbb\xbf" if bom else b"") + out.encode("utf-8"))
    return report


def main(apply):
    total = 0
    for d in DIRS:
        for path in sorted(glob.glob(f"{d}/*.txt")):
            path = path.replace("\\", "/")
            if os.path.basename(path) in HOD_FILES or not os.path.exists(f"{V}/{path}"):
                continue
            rep = sync_file(path, apply)
            if rep:
                total += len(rep)
                print(f"### {path} ({len(rep)})")
                print("\n".join(rep))
    print(f"{total} changes", "applied" if apply else "(dry run)")


if __name__ == "__main__":
    main(sys.argv[1:] == ["apply"])
