"""Character portraits not drawn yet -> the game's unknown-leader picture, planned path kept as a comment.

    python -B "plans & scripts/portrait_placeholders.py"            missing large portraits -> placeholder (+ WIPGFX/portraits_planned.csv)
    python -B "plans & scripts/portrait_placeholders.py" --restore  placeholders whose planned file now exists -> that file

User choice 2026-11-10: one shared placeholder instead of 1,234 "missing texture" errors in error.log.
"""
import csv, glob, os, re, sys

MOD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = "F:/SteamLibrary/steamapps/common/Hearts of Iron IV"
MALE, FEMALE = "gfx/leaders/leader_unknown.dds", "gfx/leaders/leader_unknown_female.dds"
TAG = "# HOD planned portrait: "


def exists(f):
    return os.path.exists(os.path.join(MOD, f)) or os.path.exists(os.path.join(GAME, f))


def placeholders():
    rows = []
    for p in sorted(glob.glob(os.path.join(MOD, "common/characters/*.txt"))):
        raw = open(p, "rb").read()
        bom = raw.startswith(b"\xef\xbb\xbf")
        s = raw.decode("utf-8-sig")
        # character blocks start at depth 1 (characters = { <id> = { ... } }); gender sits in the block
        starts = [m.start() for m in re.finditer(r"(?m)^\t(\w+)\s*=\s*\{", s)] + [len(s)]
        out, pos = [], 0
        for a, b in zip(starts, starts[1:]):
            block = s[a:b]
            female = re.search(r"gender\s*=\s*female", block) is not None

            def swap(m):
                f = m.group(2)
                if exists(f) or TAG in m.group(0):
                    return m.group(0)
                rows.append((os.path.basename(p), re.match(r"\t(\w+)", block).group(1), f))
                return '%s"%s" %s%s' % (m.group(1), FEMALE if female else MALE, TAG, f)
            out.append(s[pos:a] + re.sub(r'(large\s*=\s*)"(gfx/leaders/[^"]+)"(?![^\n]*' + re.escape(TAG) + ")", swap, block))
            pos = b
        s2 = "".join(out) + s[pos:]
        # the comment must end the line, or it eats one-line blocks' closing braces (CIS.txt 2026-11-10)
        s2 = re.sub(r"(?m)" + re.escape(TAG) + r"(\S+)[ \t]+(\S[^\n]*)$", lambda m: m.group(2) + " " + TAG + m.group(1), s2)
        if s2 != s:
            open(p, "wb").write((b"\xef\xbb\xbf" if bom else b"") + s2.encode("utf-8"))
    out = os.path.join(os.path.dirname(MOD), "ProjectKessilianWIPGFX", "portraits_planned.csv")
    new = not os.path.exists(out)
    with open(out, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["file", "character", "planned_portrait"])
        w.writerows(rows)
    print("placeholders:", len(rows), "->", out)


def restore():
    n = 0
    for p in glob.glob(os.path.join(MOD, "common/characters/*.txt")):
        raw = open(p, "rb").read()
        bom = raw.startswith(b"\xef\xbb\xbf")
        s = raw.decode("utf-8-sig")

        def back(m):
            nonlocal n
            if not exists(m.group(3)):
                return m.group(0)
            n += 1
            return '%s"%s"%s' % (m.group(1), m.group(3), m.group(2).rstrip())
        # groups: 1 `large = `, 2 rest of the line before the comment (e.g. ` } }`), 3 planned path
        s2 = re.sub(r'(large\s*=\s*)"gfx/leaders/leader_unknown(?:_female)?\.dds"([^\n#]*)' + re.escape(TAG) + r"(\S+)", back, s)
        if s2 != s:
            open(p, "wb").write((b"\xef\xbb\xbf" if bom else b"") + s2.encode("utf-8"))
    print("restored:", n)


if __name__ == "__main__":
    restore() if "--restore" in sys.argv else placeholders()
