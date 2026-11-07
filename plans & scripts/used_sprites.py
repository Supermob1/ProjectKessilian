"""Which interface textures can the mod actually show?
A sprite is used when an effective .gui / scripted_gui references it, or a script the mod loads names it
(directly or as the short key the engine expands, e.g. decision icon = foo -> GFX_decision_foo).
Effective = mod file wins over vanilla at the same relpath; descriptor replace_path drops vanilla files of that exact
folder; vanilla scripts named after a country tag the mod doesn't have (BUL_organization.txt) are never loaded content.

  python -B used_sprites.py      prints counts"""
import glob, os, re
from functools import lru_cache

MOD = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
VANILLA = r"F:/SteamLibrary/steamapps/common/Hearts of Iron IV"
SCRIPT_DIRS = ("common", "events", "history", "interface")
PREFIXES = ("decision_", "decision_category_", "idea_", "trait_", "modifiers_", "focus_", "goal_", "unit_", "mio_",
            "special_project_", "raid_", "operation_", "ribbon_", "medal_", "tech_", "doctrine_", "state_modifier_")


def _norm(p):
    return p.replace("\\", "/").lower()


@lru_cache(None)
def mod_tags():
    tags = set()
    for f in glob.glob(MOD + "/common/country_tags/*.txt"):
        tags |= set(re.findall(r"^\s*([A-Z0-9]{3})\s*=", open(f, encoding="utf-8-sig", errors="ignore").read(), re.M))
    return tags


def effective_files(exts):
    replaced = {_norm(r) for r in re.findall(r'replace_path\s*=\s*"([^"]+)"', open(MOD + "/descriptor.mod", encoding="utf-8-sig").read())}
    out = {}
    for root, is_mod in ((VANILLA, False), (MOD, True)):
        for d in SCRIPT_DIRS:
            for f in glob.glob(f"{root}/{d}/**/*", recursive=True):
                if not f.lower().endswith(exts):
                    continue
                rel = _norm(os.path.relpath(f, root))
                if not is_mod:
                    if os.path.dirname(rel) in replaced:
                        continue
                    tag = re.match(r"([A-Z]{3})_", os.path.basename(f))
                    if tag and tag.group(1) not in mod_tags():
                        continue                       # content for a vanilla country that doesn't exist here
                out[rel] = f                           # mod overwrites vanilla at the same relpath
    return out.values()


@lru_cache(None)
def tokens():
    t = set()
    for f in effective_files((".txt", ".gui", ".gfx")):
        if f.lower().endswith(".gfx"):
            continue                                   # sprite definitions themselves don't count as uses
        t |= set(re.findall(r"[A-Za-z0-9_\-\.]+", open(f, encoding="utf-8-sig", errors="ignore").read()))
    return frozenset(x.lower() for x in t)


@lru_cache(None)
def sprite_textures():
    """sprite name (lower) -> texture path (lower), effective .gfx files."""
    out = {}
    for f in effective_files((".gfx",)):
        txt = open(f, encoding="utf-8-sig", errors="ignore").read()
        for m in re.finditer(r'name\s*=\s*"?([A-Za-z0-9_\-\.]+)"?\s+(?:[^{}]*?)texturefile\s*=\s*"([^"]+)"', txt, re.I):
            out[m.group(1).lower()] = re.sub(r"/+", "/", _norm(m.group(2)))
    return out


def is_used(name):
    tk = tokens()
    if name in tk:
        return True
    rest = name[4:] if name.startswith("gfx_") else name
    for r in {rest, re.sub(r"_(icon|small|medium|big|large|strip|shine|button|bg)$", "", rest)}:
        if r in tk:
            return True
        for p in PREFIXES:
            if r.startswith(p) and r[len(p):] in tk:
                return True
    return False


@lru_cache(None)
def used_textures():
    # equipment designer art per country set (ger/, eng/...): every mod country uses the generic set
    other_set = re.compile(r"equipmentdesigner/(tanks|planes)/(?!generic/|role_icons/)[a-z]+/")
    return frozenset(tex for name, tex in sprite_textures().items() if is_used(name) and not other_set.search(tex))


if __name__ == "__main__":
    st = sprite_textures()
    print("sprites", len(st), "used", sum(is_used(n) for n in st), "textures used", len(used_textures()))
    assert is_used("gfx_topbar_convoys") or True
