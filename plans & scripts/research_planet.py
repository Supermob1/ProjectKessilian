"""Research one planet for /make-planet: Wookieepedia (canon page, /Legends page, the places its infobox links, its
battles, its image category) fetched through the MediaWiki API, cached, and boiled down to a short dossier.
    python -B "WIPGFX/plans & scripts/research_planet.py" Felucia              cached run (fetches only what is missing)
    python -B "WIPGFX/plans & scripts/research_planet.py" Felucia --refresh    re-check revisions, retry failed sources
    python -B "WIPGFX/plans & scripts/research_planet.py" Felucia --gaps       targeted searches for the open gaps
    python -B "WIPGFX/plans & scripts/research_planet.py" --selftest
Writes only under WIPGFX/research/: <planet>/{dossier.md, facts.json, sources.json, research_gaps.md, references/}
and _cache/ (raw API responses: page text keyed by revision id, metadata for TTL_DAYS, failures for RETRY_HOURS).
Canon and Legends are kept apart: facts carry their continuity, infobox differences are listed, never merged.
Text from Wookieepedia is CC BY-SA 3.0 (attribution in sources.json); images are mostly fair-use uploads (licensing
template recorded) and are kept as private references only.
"""
import argparse, hashlib, json, os, re, sys, time
from datetime import datetime, timedelta, timezone

API = "https://starwars.fandom.com/api.php"
WIKI = "https://starwars.fandom.com/wiki/"
UA = "HeartsOfDurasteel-research/1.0 (personal HOI4 modding tool; python-requests)"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "WIPGFX", "research")
CACHE = os.path.join(OUT, "_cache")
TTL_DAYS, RETRY_HOURS, MIN_GAP_S, TIMEOUT_S, TRIES = 14, 24, 1.0, 20, 3
MAX_PLACES, MAX_BATTLES, MAX_IMAGES, PER_SECTION = 10, 6, 12, 3
GLANCE = ("region", "sector", "climate", "terrain", "interest", "cities", "flora", "fauna", "species", "population",
          "affiliation", "government")                          # the infobox fields the dossier shows (all in facts.json)
NOT_INFOBOX = {"Interlang", "Top", "Quote", "Eras", "Otheruses", "Youmay", "Dialogue", "Sidebar"}
TEXT_LICENSE = "CC BY-SA 3.0 (Wookieepedia text; attribute the page URL)"
DESIGN = re.compile(r"\b(?:jungles?|forests?|swamps?|marsh\w*|fung\w*|plants?|trees?|vegetation|cit(?:y|ies)|"
                    r"villages?|towns?|settlements?|capital|outposts?|bases?|facilit(?:y|ies)|fortress\w*|compounds?|"
                    r"prisons?|detention|headquarters|spaceports?|landing|ruins?|temples?|graveyards?|abyss|caves?|"
                    r"mountains?|hills?|rivers?|lakes?|seas?|oceans?|plains?|valleys?|canyons?|terrain|surface|"
                    r"orbit\w*|blockade|trade route|walls?|population|farm\w*|harvest\w*|natives?|coloni\w*|"
                    r"govern\w*|control\w*|occup\w*|garrison\w*|army|armies|legion|tanks?|walkers?|artillery|"
                    r"front|theater|siege|supply|nysillin|ores?|mines?|mining|climate|humid|atmosphere|Separatists?|"
                    r"Republic|Confedera\w*|Commerce Guild|Empire|Imperial|Hutts?)\b", re.I)
LANDSCAPE = re.compile(r"\b(?:jungle|forest|swamp|fung\w*|plants?|trees?|flora|vegetation|sky|ground|rocks?|"
                       r"cliffs?|water|landscape|buildings?|structures?|architecture|cit(?:y|ies)|world|planet|"
                       r"surface|terrain)\b", re.I)
CW = re.compile(r"Clone Wars|\b(?:22|21|20|19) BBY\b|Separatist|Confedera|clone trooper|Grand Army|Order 66|Outer Rim Siege", re.I)
HEDGE = re.compile(r"\b(?:may|might|possibly|perhaps|rumou?red|unknown|unclear|speculat|apparently|allegedly|"
                   r"it is (?:not )?known)\b", re.I)
SKIP_SECTIONS = re.compile(r"Appearances|Sources|Notes and references|External links|Explanatory notes|Collections|"
                           r"Non-canon|Bibliography|Further reading|Gallery", re.I)
# fact categories: the first that matches a sentence wins (order = priority)
CATEGORIES = [
    ("battles", r"\b(?:battle|siege|invasion|invaded|assault|attack|bombard|skirmish|blockade|campaign|fought|"
                r"Order 66|massacre|offensive|fighting|fought|fight)\b"),
    ("political", r"\b(?:controlled|control of|government|ruled|occupied|occupation|allied|member world|joined|"
                  r"seceded|Commerce Guild|Separatists?|Confederacy|Galactic Republic|Republic|Empire|Imperial|Hutt|"
                  r"cartel|syndicate|guild|governor|sovereign)\b"),
    ("settlements", r"\b(?:city|cities|capital|town|village|settlement|colony|colonists|outpost|spaceport|"
                    r"farm|farmers|plantation|population|inhabitants|natives?)\b"),
    ("landmarks", r"\b(?:temple|palace|ruins?|monument|tower|facility|compound|fortress|arena|base|citadel|"
                  r"complex|prison|detention|refinery|factory|shrine|tomb|statue)\b"),
    ("visual", r"\b(?:colou?r(?:ful|ed)?|bright|vivid|glow(?:ing)?|bioluminescent|towering|giant|enormous|huge|"
               r"massive|tall|red|orange|yellow|purple|violet|pink|blue|green|teal|white|black|grey|gray|brown)\b"),
    ("biomes", r"\b(?:jungle|forest|fung(?:us|i|al)|plants?|flora|vegetation|trees?|swamp|marsh|bog|desert|tundra|"
               r"ice|snow|grassland|savanna|plains?|steppe|reef|coral|fauna|wildlife|creatures?|predators?)\b"),
    ("geography", r"\b(?:mountains?|ocean|seas?|continents?|valley|canyon|plateau|crater|islands?|rivers?|lakes?|"
                  r"hemisphere|pole|equator|coast|cliffs?|caves?|volcan\w*|surface|terrain|climate|atmosphere|"
                  r"moons?|orbit|north|south|east|west)\b"),
]
GEN_TERRAIN = {"jungle": "jungle", "swamp": "marsh", "marsh": "marsh", "bog": "marsh", "forest": "forest",
               "fung": "forest", "desert": "desert", "dune": "desert", "mountain": "mountain", "hill": "hills",
               "canyon": "hills", "plain": "plains", "grass": "plains", "savanna": "plains", "city": "urban",
               "cityscape": "urban", "tundra": "plains", "ice": "mountain", "volcan": "mountain", "ocean": "(sea)"}
REGION = re.compile(r"(?:was|were) (?:an?|the) (?:[\w-]+ ){0,2}(?:area|region|province|continent|highlands?|plains?|"
                    r"desert|valley|range|sea|ocean|forest|jungle|steppes?|wastes?)\b", re.I)
SETTLE = re.compile(r"\b(?:city|village|town|settlement|capital|colony|township)\b", re.I)
MILITARY = re.compile(r"\b(?:outpost|base|command|fortress|garrison|detention|prison|facility|headquarters|"
                      r"compound|bunker|stronghold|camp|depot|factory|refinery)\b", re.I)
IMG_SCENE = re.compile(r"landscape|surface|vista|aerial|panoram|jungle|forest|swamp|fung|plant|flora|terrain|"
                       r"valley|mountain|desert|canyon|cliff|scenery|concept art|matte|environment", re.I)
IMG_PLACE = re.compile(r"city|village|temple|facility|base|ruins?|settlement|outpost|compound|prison", re.I)
IMG_BAD = re.compile(r"logo|icon|favicon|template|\bSWL\b|-SWL|Legion|micro|minifig|kinect|card|SWCT|Topps|LEGO|"
                     r"portrait|headshot|\.svg$|Tab-|GoTo|Premium-Eras|Databank title|piloting|shot to death|cockpit", re.I)

log_lines, stats = [], {"api": 0, "api_cached": 0, "fail": 0, "skipped_failed": 0, "img_new": 0, "img_cached": 0}


def log(msg):
    log_lines.append(msg)
    print(msg)


def now():
    return datetime.now(timezone.utc)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def jload(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def jsave(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    json.dump(obj, open(tmp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    os.replace(tmp, path)


# ---------------------------------------------------------------- fetching: polite, bounded, cached
class Fetcher:
    def __init__(self, refresh):
        import requests
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.refresh, self.last, self.last_error = refresh, 0.0, ""
        self.fail_path = os.path.join(CACHE, "failures.json")
        self.failures = jload(self.fail_path, {})

    def _get(self, url, params=None, binary=False):
        """one GET with TRIES attempts (back-off, Retry-After honoured up to 30 s); None when it keeps failing"""
        key = url + "?" + json.dumps(params, sort_keys=True) if params else url
        f = self.failures.get(key)
        if f and not self.refresh and now() - datetime.fromisoformat(f["when"]) < timedelta(hours=RETRY_HOURS):
            stats["skipped_failed"] += 1
            return None
        err = ""
        for attempt in range(TRIES):
            time.sleep(max(0.0, self.last + MIN_GAP_S - time.time()))
            self.last = time.time()
            try:
                r = self.s.get(url, params=params, timeout=TIMEOUT_S)
                stats["api"] += 1
                if r.status_code == 200:
                    self.failures.pop(key, None)
                    return r.content if binary else r.json()
                err = f"HTTP {r.status_code}"
                if r.status_code not in (429, 500, 502, 503, 504):
                    break                                                   # 4xx: retrying will not help
                wait = r.headers.get("Retry-After", "")
                time.sleep(min(30, int(wait) if wait.isdigit() else 2 ** (attempt + 1)))
            except Exception as e:                                          # noqa: BLE001  timeouts, DNS, bad JSON
                err = f"{type(e).__name__}: {str(e)[:120]}"
                time.sleep(2 ** (attempt + 1))
        stats["fail"] += 1
        self.last_error = err
        self.failures[key] = {"when": now().isoformat(), "error": err}
        jsave(self.fail_path, self.failures)
        log(f"  unavailable: {key[:110]} ({err}); not retried for {RETRY_HOURS} h unless --refresh")
        return None

    def api(self, ttl=True, **params):
        """API query; cached for TTL_DAYS when ttl, forever when ttl=False (callers key those by revision id)"""
        params = dict(params, format="json", formatversion=2)
        path = os.path.join(CACHE, "api", hashlib.sha1(json.dumps(params, sort_keys=True).encode()).hexdigest() + ".json")
        hit = jload(path, None)
        if hit and not (ttl and (self.refresh or now() - datetime.fromisoformat(hit["fetched"]) > timedelta(days=TTL_DAYS))):
            stats["api_cached"] += 1
            return hit["data"]
        data = self._get(API, params)
        if data is None:
            return hit["data"] if hit else None                           # stale beats nothing
        jsave(path, {"fetched": now().isoformat(), "params": params, "data": data})
        return data

    def pages(self, titles):
        """{title: dict(title, revid, timestamp, text, missing)}: revisions looked up (TTL), text cached per revid"""
        out = {}
        titles = list(dict.fromkeys(titles))
        for i in range(0, len(titles), 50):
            meta = self.api(action="query", prop="revisions", rvprop="ids|timestamp", redirects=1,
                            titles="|".join(titles[i:i + 50]))
            if meta is None:
                for t in titles[i:i + 50]:
                    out[t] = dict(title=t, missing=True, unavailable=True)
                continue
            q = meta.get("query", {})
            alias = {r["from"]: r["to"] for r in q.get("redirects", []) + q.get("normalized", [])}
            got = {}
            for p in q.get("pages", []):
                if p.get("missing") or not p.get("revisions"):
                    got[p["title"]] = dict(title=p["title"], missing=True)
                    continue
                rv = p["revisions"][0]
                text = self.api(ttl=False, action="query", prop="revisions", rvprop="content", rvslots="main",
                                revids=rv["revid"])
                body = None
                if text:
                    body = text["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
                got[p["title"]] = dict(title=p["title"], revid=rv["revid"], timestamp=rv["timestamp"], text=body,
                                       missing=body is None, unavailable=body is None)
            for t in titles[i:i + 50]:
                tt = t
                while tt in alias:
                    tt = alias[tt]
                out[t] = got.get(tt, dict(title=t, missing=True))
        return out


# ---------------------------------------------------------------- wikitext
def balanced(s, start):
    """index after the template that opens at s[start] ('{{')"""
    d, i = 0, start
    while i < len(s) - 1:
        if s.startswith("{{", i):
            d, i = d + 1, i + 2
        elif s.startswith("}}", i):
            d, i = d - 1, i + 2
            if d == 0:
                return i
        else:
            i += 1
    return len(s)


def clean(s):
    """wikitext -> plain text: refs, comments, files, templates go ({{C|x}} -> (x)); links -> their label"""
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"<ref[^>/]*/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\[\[(?:File|Image|Category):[^\[\]]*(?:\[\[[^\]]*\]\][^\[\]]*)*\]\]", "", s)
    s = re.sub(r"\{\{C\|([^{}]*)\}\}", r"(\1)", s)
    s = re.sub(r"\{\{(?:Film|TCW|SWE|DB|BuildFalconCite|GermanFanCite)\|[^{}]*\}\}", "", s)
    while "{{" in s:
        i = s.rfind("{{")
        j = s.find("}}", i)
        if j < 0:
            break
        s = s[:i] + s[j + 2:]
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[https?://\S+ ([^\]]*)\]", r"\1", s)
    s = re.sub(r"<br\s*/?>", "; ", s)
    s = re.sub(r"\(\s*(?:or\s*)?/[^/)]*/\s*\)|\(\s*(?:or)?\s*\)", "", s)        # IPA / empty brackets
    s = re.sub(r"<[^>]+>", "", s).replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", s).strip(" *;")


def links(s):
    return [m.split("#")[0].strip() for m in re.findall(r"\[\[([^\]|]+)", s)
            if not re.match(r"(?:File|Image|Category):", m)]


def infobox(w, names=None):
    """(template name, {field: dict(text, links, cited)}) of the first infobox template"""
    m = next((m for m in re.finditer(r"\{\{\s*(" + (names or r"[A-Z][A-Za-z ]+") + r")\s*\n", w)
              if m.group(1).strip() not in NOT_INFOBOX), None)
    if not m:
        return None, {}
    body = w[m.end():balanced(w, m.start()) - 2]
    fields, d, cur = {}, 0, None
    buf = ""
    for line in body.split("\n"):
        if d == 0 and line.startswith("|"):
            if cur:
                fields[cur] = buf
            k, _, v = line[1:].partition("=")
            cur, buf = k.strip(), v
        else:
            buf += "\n" + line
        d += line.count("{{") - line.count("}}")
    if cur:
        fields[cur] = buf
    items = lambda v: re.sub(r"(?:^|\n)\s*\*+\s*", ", ", v.strip()).strip(", ")
    return m.group(1).strip(), {k: dict(text=clean(items(v)), links=links(re.sub(r"\{\{C\|[^{}]*\}\}", "", v)),
                                        cited="<ref" in v)
                                for k, v in fields.items() if clean(v)}


def sections(w):
    """[(heading path, raw text)]: the lead ('Lead') and every section, minus the out-of-scope ones"""
    out, path = [], []
    parts = re.split(r"^(=+)\s*(.*?)\s*=+\s*$", w, flags=re.M)
    lead = parts[0]
    m = re.search(r"\{\{\s*[A-Z][A-Za-z ]+\s*\n\|", lead)                 # drop the infobox from the lead
    if m:
        lead = lead[:m.start()] + lead[balanced(lead, m.start()):]
    out.append(("Lead", lead))
    for k in range(1, len(parts), 3):
        level = len(parts[k]) - 2
        path = path[:max(level, 0)] + [parts[k + 1]]
        if not any(SKIP_SECTIONS.search(h) for h in path):
            out.append((" > ".join(path), parts[k + 2]))
    return out


def strip_templates(s):
    """{{C|x}} -> (x); every other template (quotes, notes, multi-line) removed whole"""
    s = re.sub(r"\{\{C\|([^{}]*)\}\}", r"(\1)", s)
    i = s.find("{{")
    while i >= 0:
        s = s[:i] + s[balanced(s, i):]
        i = s.find("{{", i)
    return s


def sentences(raw):
    """[(plain sentence, cited, links)] of a section"""
    res = []
    raw = strip_templates(raw)
    for para in re.split(r"\n\s*\n|\n(?=[*#:])", raw):
        cited_para = "<ref" in para
        for chunk in re.split(r"(?<=[.!?])(?:<ref[^>]*/>|<ref[^>]*>.*?</ref>)*\s+(?=[A-Z\"'\[])", para, flags=re.S):
            t = clean(chunk)
            if len(t) >= 25 and not t.startswith(("Main article", "See also")):
                res.append((t, "<ref" in chunk or cited_para, links(chunk)))
    return res


def norm(s):
    return set(re.findall(r"[a-z0-9]+", s.lower())) - {"the", "a", "an", "of", "and", "in", "on", "to", "was", "is"}


def similar(a, b):
    a, b = norm(a), norm(b)
    return len(a) >= 4 and len(b) >= 4 and len(a & b) / len(a | b) >= 0.75


# ---------------------------------------------------------------- facts
def continuity(page):
    """'legends' for '<title>/Legends' and for Legends-only articles ({{Top|leg}}), else 'canon'"""
    top = re.search(r"\{\{Top\|([^}]*)\}\}", page.get("text") or "")
    legends = page["title"].endswith("/Legends") or bool(top and "leg" in top.group(1).split("|"))
    return "legends" if legends else "canon"


def year_era(text):
    """era of the first dated year in text ('20 BBY', '27,000 BBY', '4 ABY'), else None"""
    m = re.search(r"\b(\d[\d,]*)\s*(BBY|ABY)\b", text)
    if not m:
        return None
    y = int(m.group(1).replace(",", "")) * (1 if m.group(2) == "BBY" else -1)
    return "before-clone-wars" if y > 22 else "clone-wars" if y >= 19 else "after-clone-wars"


def era(section, text):
    """out-of-universe | before-clone-wars | clone-wars | after-clone-wars | timeless (descriptions) | unspecified"""
    if re.search(r"Behind the scenes", section, re.I):
        return "out-of-universe"
    if section == "Infobox":
        return "all-eras"                                                 # an infobox value spans the eras
    by_year = year_era(text)
    if by_year:
        return by_year
    if re.search(r"(?:after|following) the (?:end of the )?Clone Wars", text, re.I):
        return "after-clone-wars"
    h = re.search(r"History > (.+)", section)
    if h:                                                                   # the history subsection's period
        if CW.search(h.group(1)):
            return "clone-wars"
        if re.search(r"Empire|Imperial|later|New Republic|Civil War|First Order|after|aftermath", h.group(1), re.I):
            return "after-clone-wars"
        if re.search(r"early|ancient|coloni|Republic Era|Old Republic|before|founding|settle", h.group(1), re.I):
            return "before-clone-wars"
    if CW.search(text):
        return "clone-wars"
    return "timeless" if re.search(r"Description|Geography|Climate|Flora|Fauna", section, re.I) else "unspecified"


def categorize(text, section):
    if re.search(r"Behind the scenes", section, re.I):
        return "production"
    for cat, rx in CATEGORIES:
        if re.search(rx, text, re.I):
            return cat
    return None


def add_fact(facts, page, kind, category, text, section, cited, linked, extra=None):
    """append a fact, or merge its evidence into an equal one of the SAME continuity (never across)"""
    cont = continuity(page)
    ev = dict(source=page["title"], url=WIKI + page["title"].replace(" ", "_"), section=section, quote=text[:300])
    for f in facts:
        if f["continuity"] == cont and f["category"] == category and similar(f["text"], text):
            if all(e["source"] != ev["source"] for e in f["evidence"]):
                f["evidence"].append(ev)
            return f
    conf = "high" if kind == "infobox" and cited else "medium" if cited or kind != "prose" else "low"
    hedged = bool(HEDGE.search(text))
    f = dict(id=f"{cont[0]}{hashlib.sha1((cont + category + text).encode()).hexdigest()[:8]}", category=category,
             text=text if len(text) <= 300 else text[:297] + "...", continuity=cont, era=era(section, text),
             confidence="low" if hedged else conf, hedged=hedged, kind=kind, entities=linked[:8], evidence=[ev])
    f.update(extra or {})
    f["design_value"], f["review"] = assess(f)
    facts.append(f)
    return f


def assess(f):
    """(design value, review flags) of a fact: how much it tells a map designer, and why it may be noise"""
    t = f["text"]
    value = len(set(m.lower() for m in DESIGN.findall(t))) + (2 if f["kind"] in ("place", "battle", "infobox") else 0)
    flags = []
    if f["kind"] == "prose":
        if t.count('"') % 2 or "|" in t or re.search(r"\b(?:I|we|you|me|my|our)\b", t) or t[:1].islower():
            flags.append("fragment")                                     # quote / dialogue residue
        if not DESIGN.search(t):
            flags.append("narrative")                                    # story beat, nothing about the place
        if f["category"] == "visual" and not LANDSCAPE.search(t):
            flags.append("weak-category")                                # a colour word, not a look of the place
    if f["kind"] == "place" and re.search(r"System|SpaceStation|Starship|Ship", f.get("infobox") or ""):
        flags.append("off-surface")
    return value, flags


def article_facts(facts, page):
    """the planet article: infobox fields (each a fact) and categorized sentences"""
    name, box = infobox(page["text"], "CelestialBody|Planet|Celestial body|Moon|Space station|Asteroid")
    for k, v in box.items():
        if k in ("image", "name") or not v["text"]:
            continue
        add_fact(facts, page, "infobox", "infobox", f"{k}: {v['text']}", "Infobox", v["cited"], v["links"],
                 {"field": k})
    for sec, raw in sections(page["text"]):
        for text, cited, linked in sentences(raw):
            cat = categorize(text, sec)
            if cat:
                add_fact(facts, page, "prose", cat, text, sec, cited, linked)
    return box


def place_facts(facts, page, role, planet):
    """a linked place (city / point of interest): its lead and the infobox fields that place it; skipped when the
    lead does not name the planet (media, generic articles linked from an infobox note)"""
    name, box = infobox(page["text"])
    lead = [s for s in sentences(sections(page["text"])[0][1])][:2]
    if not lead or name in ("Character", "Droid", "Species", "Organization", "Military unit", "Company"):
        return                                                              # linked from a place name, not a place
    if planet.lower() not in (" ".join(t for t, _, _ in lead) + page["title"]).lower():
        return
    detail = {k: box[k]["text"][:120] for k in ("type", "location", "planet", "region", "constructed", "destroyed",
                                               "affiliation", "owner", "population") if k in box}
    text = " ".join(t for t, _, _ in lead)
    first = text.split(". ")[0]                                          # what the place itself is
    site = ("orbital" if re.search(r"System|SpaceStation|Starship", name or "") or re.search(r"\borbit", first) else
            "settlement" if role == "cities" or name in ("City", "Settlement") else
            "region" if REGION.search(first) else
            "military" if MILITARY.search(first) or MILITARY.search(detail.get("type", "")) or name == "Structure" else
            "settlement" if SETTLE.search(first) else "landmark")
    f = add_fact(facts, page, "place", "settlements" if site == "settlement" else "landmarks", text, "Lead",
                 any(c for _, c, _ in lead), [l for _, _, ls in lead for l in ls],
                 {"place": page["title"].replace("/Legends", ""), "infobox": name, "details": detail, "site": site,
                  "role": role})
    built, gone = year_era(detail.get("constructed", "")), year_era(detail.get("destroyed", ""))
    if gone == "before-clone-wars" or built == "after-clone-wars":
        f["era"], f["review"] = ("before-clone-wars" if gone == "before-clone-wars" else "after-clone-wars"), \
            f["review"] + ["not-in-clone-wars"]


def battle_facts(facts, page, planet):
    name, box = infobox(page["text"], "Battle|Conflict|Battle infobox|Campaign")
    if not box:
        return
    place = box.get("place", {}).get("text", "")
    if planet.lower() not in (place + page["title"]).lower():
        return                                                              # a search hit that is not about here
    pick = lambda *ks: next((box[k]["text"][:160] for k in ks if k in box), "")
    lead = sentences(sections(page["text"])[0][1])[:1]
    add_fact(facts, page, "battle", "battles", lead[0][0] if lead else page["title"], "Lead", True, [],
             {"battle": page["title"].replace("/Legends", ""), "date": pick("date"), "place": place[:160],
              "outcome": pick("result", "outcome"), "side1": pick("side1", "combatants1"),
              "side2": pick("side2", "combatants2"), "war": pick("conflict")})
    facts[-1]["era"] = "clone-wars" if CW.search(json.dumps(box)) else facts[-1]["era"]


# ---------------------------------------------------------------- images
def image_candidates(fx, planet, keywords):
    """every file in 'Category:Images of <planet>': url, thumb, description, source, licensing; scored"""
    files, cont = [], {}
    while True:
        r = fx.api(action="query", list="categorymembers", cmtitle=f"Category:Images of {planet}", cmtype="file",
                   cmlimit=500, **cont)
        if not r:
            break
        files += [m["title"] for m in r["query"]["categorymembers"]]
        if "continue" not in r:
            break
        cont = {"cmcontinue": r["continue"]["cmcontinue"]}
    out = []
    for i in range(0, len(files), 50):
        r = fx.api(action="query", prop="imageinfo|revisions", iiprop="url|size|mime|timestamp", iiurlwidth=640,
                   rvprop="content", rvslots="main", titles="|".join(files[i:i + 50]))
        for p in (r or {}).get("query", {}).get("pages", []):
            ii = (p.get("imageinfo") or [{}])[0]
            w = (p.get("revisions") or [{}])[0].get("slots", {}).get("main", {}).get("content", "")
            field = lambda k: (re.search(rf"\|\s*{k}\s*=(.*?)(?=\n\|[a-z ]+=|\n\}}\}})", w, re.S) or [None, ""])[1]
            desc, src, lic = clean(field("description")), clean(field("source")), field("licensing")
            name = p["title"][5:]
            text = f"{name} {desc}"
            score = (4 * bool(IMG_SCENE.search(text)) + 2 * bool(IMG_PLACE.search(text)) + bool(re.search("battle", text, re.I))
                     + sum(2 for k in keywords if k.lower() in text.lower()) + (ii.get("width", 0) >= 600)
                     + bool(re.search(r"screenshot|concept", lic + src, re.I)) - 6 * bool(IMG_BAD.search(name + " " + src + " " + desc)))
            out.append(dict(file=p["title"], page=ii.get("descriptionurl", WIKI + p["title"].replace(" ", "_")),
                            original=ii.get("url"), thumb=ii.get("thumburl"), width=ii.get("width"),
                            height=ii.get("height"), mime=ii.get("mime"), uploaded=ii.get("timestamp"),
                            description=desc[:300], source=src[:300],
                            licensing=", ".join(re.findall(r"\{\{\s*([^|}]+)", lic)) or "not stated",
                            redistribution="not cleared: wiki upload, usually fair-use material; private reference only",
                            score=score))
    out.sort(key=lambda c: (-c["score"], c["file"]))
    return out


def download_images(fx, cands, folder, n):
    """thumbnails of the n best candidates; stops at the first refusal (the CDN may refuse automated clients: that
    is respected, not worked around) and returns that note, else None"""
    os.makedirs(folder, exist_ok=True)
    for c in cands[:n]:
        if c["score"] <= 0 or not c["thumb"]:
            continue
        ext = os.path.splitext(c["file"])[1].lower() or ".png"
        name = slug(c["file"][5:].rsplit(".", 1)[0])[:60] + ext
        path = os.path.join(folder, name)
        c["local"] = f"references/{name}"
        if os.path.exists(path) and c.get("uploaded") and os.path.getsize(path):
            stats["img_cached"] += 1
            continue
        data = fx._get(c["thumb"], binary=True)
        if data:
            open(path, "wb").write(data)
            stats["img_new"] += 1
        else:
            c.pop("local")
            if fx.last_error.startswith("HTTP 4") or stats["skipped_failed"]:
                return (f"image downloads refused by {c['thumb'].split('/')[2]} ({fx.last_error or 'failed recently'}); "
                        "links kept, open the file pages to view")
    return None


# ---------------------------------------------------------------- gaps
def gaps(planet, facts, images):
    """what a battlefield design still needs, with targeted follow-up searches"""
    canon = [f for f in facts if f["continuity"] == "canon"]
    has = lambda cat, fs=canon: [f for f in fs if f["category"] == cat]
    field = lambda k: next((f for f in canon if f.get("field") == k), None)
    dirs = [f for f in canon if re.search(r"\b(?:north|south|east|west|hemisphere|pole|equator)", f["text"], re.I)]
    out = []

    def gap(gid, ok, question, why, queries, partial=False):
        out.append(dict(id=gid, status="covered" if ok else "partial" if partial else "open", question=question,
                        why=why, searches=[q.replace("{p}", planet) for q in queries]))
    gap("settlements", field("cities") and has("settlements"), "Which settlements exist (capital, towns) and what "
        "do they look like?", "state capitals, VP names, city models", ["{p} city", "{p} settlement", "{p} village"],
        partial=bool(field("cities") or has("settlements")))
    gap("landmarks", len([f for f in canon if f["kind"] == "place" and f["category"] == "landmarks"]) >= 3,
        "Which named landmarks / facilities stand on the planet?", "VPs and landmark models",
        ["{p} facility", "{p} temple", "{p} base", "{p} ruins"], partial=bool(field("interest")))
    gap("biomes", field("terrain") and has("biomes"), "Which biomes cover the surface, in what proportion?",
        "terrain mix and zones", ["{p} jungle", "{p} terrain"], partial=bool(field("terrain")))
    gap("layout", len(dirs) >= 2, "Where are things relative to each other (hemispheres, coasts, regions)?",
        "placing zones and states; canon rarely gives a map, so most layout will be a labelled design choice",
        ["{p} northern", "{p} southern", "{p} region", "{p} continent"], partial=bool(dirs))
    gap("clone_wars_control", any(f["era"] == "clone-wars" for f in has("political")),
        "Who controlled the planet and its regions during the Clone Wars?", "owners, cores, starting armies",
        ["{p} Separatist", "{p} Commerce Guild", "{p} Republic"], partial=bool(field("affiliation")))
    gap("battles", any(f["kind"] == "battle" and f["era"] == "clone-wars" for f in facts),
        "Which Clone Wars battles happened there, and where on the planet?", "battlefield focus, events",
        ["Battle of {p}", "{p} campaign"])
    gap("visuals", sum(1 for c in images if c["score"] > 0) >= 6, "Are there enough landscape / landmark images?",
        "terrain colours and model shapes", ["{p} concept art", "{p} landscape"],
        partial=any(c["score"] > 0 for c in images))
    conflicts = [f for f in facts if f.get("conflict")]
    if conflicts:
        out.append(dict(id="continuity", status="decision", question="Canon and Legends disagree on: " +
                        ", ".join(sorted({f['field'] for f in conflicts})) + ". Which one does the mod follow?",
                        why="the dossier never merges them; the user / design picks", searches=[]))
    return out


def mark_conflicts(facts):
    """infobox fields present in both continuities with different values: flagged on both facts"""
    by = {}
    for f in facts:
        if f.get("field"):
            by.setdefault(f["field"], {})[f["continuity"]] = f
    for k, d in by.items():
        a, b = (d[c]["text"].split(": ", 1)[-1] for c in ("canon", "legends")) if len(d) == 2 else ("", "")
        nums = lambda t: set(re.findall(r"\d[\d,.]*", t))
        if len(d) == 2 and (nums(a) != nums(b) or len(norm(a) & norm(b)) < 0.5 * len(norm(a) | norm(b))):
            d["canon"]["conflict"] = d["legends"]["conflict"] = True


# ---------------------------------------------------------------- outputs
def link(title):
    return f"[{title}]({WIKI + title.replace(' ', '_')})"


def pick(facts, cat, cont, n=PER_SECTION):
    fs = [f for f in facts if f["category"] == cat and f["continuity"] == cont and f["kind"] != "battle"  # tabulated
          and not set(f["review"]) & {"fragment", "narrative", "weak-category", "off-surface"}]
    rank = {"high": 0, "medium": 1, "low": 2}
    fs.sort(key=lambda f: (f["era"] != "clone-wars", rank[f["confidence"]], -f["design_value"], f["kind"] == "prose",
                           -len(f["evidence"])))
    return fs[:n]


def bullet(f):
    tags = [f["era"]] if f["era"] in ("clone-wars", "out-of-universe") else []
    tags += ["low confidence"] if f["confidence"] == "low" else []
    text = f["text"] if len(f["text"]) <= 200 else f["text"][:197] + "..."
    return f"- {text} ({'; '.join(tags) + '; ' if tags else ''}{link(f['evidence'][0]['source'])})"


def write_dossier(path, planet, facts, srcs, images, gap_list, img_note, max_images):
    L = [f"# {planet}: research dossier",
         f"Generated {now():%Y-%m-%d} by research_planet.py from {len([s for s in srcs if s['status'] == 'ok'])} "
         f"Wookieepedia pages ({TEXT_LICENSE}). Canon first; Legends only where labelled; the two are never merged. "
         "Every line is sourced; the only inferences are in the section marked INFERENCE.", ""]
    box = {}
    for f in facts:
        if f.get("field"):
            box.setdefault(f["field"], {})[f["continuity"]] = f
    if box:
        L += ["## At a glance (infoboxes)", "| field | canon | Legends |", "|---|---|---|"]
        for k, d in ((k, box[k]) for k in GLANCE if k in box):
            v = lambda c: d[c]["text"].split(": ", 1)[1][:80] if c in d else ""
            L.append(f"| {k}{' (differs)' if d.get('canon', d.get('legends')).get('conflict') else ''} | {v('canon')} | {v('legends')} |")
        L.append("")
    titles = {"political": "Political control", "battles": "Battles and events", "settlements": "Settlements",
              "landmarks": "Landmarks and facilities", "biomes": "Biomes, flora and fauna", "geography": "Geography",
              "visual": "Visual appearance", "production": "Behind the scenes (out of universe)"}
    for cat, title in titles.items():
        block = []
        for cont in ("canon", "legends"):
            fs = pick(facts, cat, cont, PER_SECTION if cat != "production" else 2 if cont == "canon" else 0)
            if fs:
                block += [f"**{cont.capitalize()}**"] + [bullet(f) for f in fs]
        if block:
            L += [f"## {title}"] + block + [""]
    battles = [f for f in facts if f["kind"] == "battle"]
    if battles:
        L += ["## Battle list", "| battle | continuity | date | outcome |", "|---|---|---|---|"]
        for f in sorted(battles, key=lambda f: (f["continuity"], f["era"] != "clone-wars", f["battle"]))[:8]:
            L.append(f"| {link(f['evidence'][0]['source'])} | {f['continuity']} | {f['date'][:40]} | {f['outcome'][:80]} |")
        L.append("")
    shown = [c for c in images if c["score"] > 0][:min(max_images, 8)]
    if shown:
        L += [f"## Image references (best {len(shown)} of {len(images)} in references/index.json; licensing not "
              "cleared, private reference only)"] + ([f"- NOTE: {img_note}"] if img_note else [])
        L += [f"- {'`' + c['local'] + '`' if c.get('local') else '[' + c['file'][5:] + '](' + c['page'] + ')'}: "
              f"{c['description'][:110] or '(no description)'} ({c['licensing']})" for c in shown] + [""]
    terr = next((f for f in facts if f.get("field") == "terrain" and f["continuity"] == "canon"), None)
    if terr:
        hits = sorted({v for k, v in GEN_TERRAIN.items() if k in terr["text"].lower()})
        L += ["## INFERENCE: HOI4 terrain hint (script keyword match, not canon)",
              f"- canon terrain '{terr['text'].split(': ', 1)[1]}' suggests HOI4 terrain: {', '.join(hits) or 'no match'}", ""]
    bad = [s for s in srcs if s["status"] != "ok"]
    if bad:
        L += ["## Sources not available"] + [f"- {s['title']}: {s['status']} {s.get('error', '')}" for s in bad] + [""]
    L += ["## Open questions",
          *[f"- [{g['status']}] {g['question']}" for g in gap_list if g["status"] != "covered"],
          "Details and follow-up searches: research_gaps.md (run with --gaps to search them)."]
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")


def write_gaps(path, planet, gap_list, attempted):
    L = [f"# {planet}: research gaps", "Status: open = nothing found, partial = some evidence, decision = needs a "
         "design choice, covered = enough for design. `--gaps` runs the searches of open/partial gaps once each.", ""]
    for g in gap_list:
        if g["status"] == "covered":
            continue
        L += [f"## {g['id']} [{g['status']}]", g["question"], f"Needed for: {g['why']}."]
        for q in g["searches"]:
            L.append(f"- search `{q}`" + (f" (searched {attempted[q][:10]})" if q in attempted else ""))
        L.append("")
    L += ["Covered: " + (", ".join(g["id"] for g in gap_list if g["status"] == "covered") or "none")]
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")


def short(t, n):
    """t cut to n chars at a word boundary, marked with '...'"""
    return t if len(t) <= n else t[:t.rfind(" ", 0, n)].rstrip(",;:") + "..."


def write_brief(path, planet, facts, images, gap_list):
    """design_brief.md: what /make-planet decides from. Only sourced items, ranked for a playable HOI4 map; the
    suggestions are labelled INFERENCE and never give positions the sources do not state."""
    tag = lambda f: f"{'C' if f['continuity'] == 'canon' else 'L'}"
    refs = {}

    def src(f):
        t = f["evidence"][0]["source"]
        refs.setdefault(t, WIKI + t.replace(" ", "_"))
        return f"[{t}]"
    places = {}
    for f in facts:                                                          # one row per place, both continuities
        if f["kind"] == "place":
            places.setdefault(f["place"], []).append(f)
    box = lambda cont, k: next((f["text"].split(": ", 1)[1] for f in facts if f.get("field") == k
                                and f["continuity"] == cont), "")
    capitals = {c: {x.strip() for x in re.findall(r"([^,]+?) \(capital\)", box(c, "cities"))} for c in ("canon", "legends")}

    def row(name, fs):
        conts = "+".join(sorted({tag(f) for f in fs}))                     # C, L or C+L (two articles, not merged)
        f = sorted(fs, key=lambda f: (f["continuity"] != "canon", -f["design_value"]))[0]
        eras = {x["era"] for x in fs}
        when = ("Clone Wars" if "clone-wars" in eras else "not in the Clone Wars" if eras & {"before-clone-wars",
                "after-clone-wars"} and not eras & {"timeless", "unspecified"} else "era not stated")
        lead = short(f["text"].split(". ")[0], 110).rstrip(".")
        return conts, when, lead, f

    def score(name, fs):
        conts, when, lead, f = row(name, fs)
        return (("C" in conts) * 4 + ("L" in conts) + (when == "Clone Wars") * 3 - (when == "not in the Clone Wars") * 4
                + any(name in capitals[c] for c in capitals) * 5 + min(f["design_value"], 4)
                - 6 * any("off-surface" in x["review"] for x in fs))

    groups = {"settlement": [], "region": [], "military": [], "landmark": [], "orbital": []}
    for name, fs in places.items():
        if any(f.get("infobox") == "System" for f in fs):
            continue                                                       # the star system itself
        site = sorted(fs, key=lambda f: f["continuity"] != "canon")[0]["site"]
        groups[site].append((score(name, fs), name, fs))
    for g in groups.values():
        g.sort(key=lambda t: (-t[0], t[1]))

    L = [f"# {planet}: design brief",
         "Decision sheet for /make-planet, generated from facts.json (no new research). C = canon article, L = Legends "
         "article, C+L = both (kept apart in facts.json). Ranked for a playable map. Nothing here gives positions on the "
         "planet unless a source states them; everything under SUGGESTION is a design choice, not lore.", ""]

    # states
    L += ["## Candidate states (anchors)",
          "A named article is not a state by itself: only capitals, major cities and named regions anchor a state; "
          "everything else is a VP inside one.", "| rank | anchor | continuity | why | source |", "|---|---|---|---|---|"]
    anchors = []
    for sc, name, fs in groups["settlement"]:
        conts, when, lead, f = row(name, fs)
        cap = [c[0].upper() for c in capitals if name in capitals[c]]
        major = any(re.search(r"\bwas (?:a|the) (?:[\w-]+ ){0,3}(?:major city|capital)", x["text"].split(". ")[0], re.I)
                    for x in fs)
        if cap or major:
            why = (f"capital ({'+'.join(cap)})" if cap else "major city") + (f"; {when}" if when != "era not stated" else "")
            anchors.append((sc, name, conts, why, src(f)))
    regions = sorted({e for f in facts if f["kind"] == "prose" and f["category"] in ("geography", "biomes")
                      for e in f["entities"] if re.search(r"Jungle|Forest|Sea|Mountains?|Plains|Valley|Highlands|"
                                                          r"Basin|Desert|Swamp|Region|Continent", e)
                      and not re.search(r"Felucian|species|rancor", e, re.I)})
    for sc, name, fs in groups["region"]:                                # named areas of the planet
        conts, when, lead, f = row(name, fs)
        anchors.append((sc - 2, name, conts, "named region" + (f"; {when}" if when != "era not stated" else ""), src(f)))
    for i, (sc, name, conts, why, s_) in enumerate(sorted(anchors, key=lambda a: -a[0]), 1):
        L.append(f"| {i} | {name} | {conts} | {why} | {s_} |")
    L += [f"- Named regions in the sources: {', '.join(regions) if regions else 'none found (state regions will be design choices)'}", ""]

    # VPs
    L += ["## Candidate victory points"]
    titles = {"settlement": "Settlements", "military": "Military sites", "landmark": "Other landmarks",
              "orbital": "Orbital (not a land VP; port / naval base flavour at most)"}
    for key, title in titles.items():
        if groups[key]:
            L.append(f"**{title}**")
            for sc, name, fs in groups[key][:2 if key == "orbital" else 6]:
                conts, when, lead, f = row(name, fs)
                L.append(f"- {name} [{conts}; {when}] {lead}. ({src(f)})")
    bat = {}
    for f in facts:
        if f["kind"] == "battle" and f["era"] == "clone-wars":
            bat.setdefault(f["battle"], []).append(f)
    if bat:
        L.append("**Battle sites** (no source places these battles at a spot on the planet)")
        yr = lambda fs: max((int(m) for f in fs for m in re.findall(r"(\d+) BBY", f["date"])), default=-999)
        for name, fs in sorted(bat.items(), key=lambda t: -yr(t[1]))[:6]:
            fs.sort(key=lambda f: f["continuity"])
            when = "; ".join(f"{tag(f)} {re.match(r'[^,(]*', f['date']).group(0).strip() or '?'}" for f in fs)
            L.append(f"- {name} [{when}] {fs[0]['outcome'][:60]} ({src(fs[0])})")
    L.append("")

    # look
    L += ["## Visual identity"]
    for k in ("terrain", "climate", "flora"):
        vals = {c: box(c, k) for c in ("canon", "legends") if box(c, k)}
        if vals:
            L.append(f"- {k}: " + "; ".join(f"{v[:70]} [{c[0].upper()}]" for c, v in vals.items()))
    look = [f for f in facts if f["category"] in ("visual", "biomes") and f["kind"] == "prose"
            and not set(f["review"]) & {"fragment", "narrative", "weak-category"}
            and re.match(r"Lead|Description", f["evidence"][0]["section"])          # descriptions, not history
            and not re.search(CATEGORIES[0][1] + r"|\bconflicts?\b|\bwar\b", f["text"], re.I)]   # no war narration
    look.sort(key=lambda f: (f["continuity"] != "canon", f["category"] != "visual", -f["design_value"]))
    for f in look[:4]:
        L.append(f"- {short(f['text'], 170)} [{tag(f)}] ({src(f)})")
    arch = [f for f in facts if re.search(r"\b(?:architecture|huts?|domes?|towers?|spires?|stilts|built (?:from|of|into|on)|"
                                          r"made (?:from|of)|style)\b", f["text"], re.I)
            and f["kind"] in ("place", "prose") and not set(f["review"]) & {"fragment", "narrative"}]
    L += [f"- architecture: {f['text'][:150]} [{tag(f)}] ({src(f)})" for f in arch[:2]] or \
        ["- architecture: not described in the sources (city / building look is a design choice)"]
    bts = [f for f in facts if f["category"] == "production" and re.search(r"concept|design|art|look", f["text"], re.I)]
    for f in bts[:2]:
        L.append(f"- out-of-universe: {short(f['text'], 150)} ({src(f)})")
    best = [c for c in images if c["score"] > 0][:4]
    if best:
        L.append("- stills to ask the user for / open: " + ", ".join(f"[{c['file'][5:]}]({c['page']})" for c in best))
    L.append("")

    # geography
    rel = re.compile(r"\b(?:near|outside|beyond|on the outskirts of|north of|south of|east of|west of|between|"
                     r"adjacent to|bordering|overlooking|surrounded by|located in|in the (?:north|south|east|west)\w*|"
                     r"hemisphere|orbit(?:ing)?)\b", re.I)
    ground = {n for n, fs in places.items() if not any("off-surface" in x["review"] for x in fs)}
    geo = [f for f in facts if f["kind"] in ("place", "prose") and rel.search(f["text"])
           and not set(f["review"]) & {"fragment", "off-surface"}
           and sum(n in f["text"] for n in ground) >= (1 if f["kind"] == "place" else 2)]
    geo.sort(key=lambda f: (f["continuity"] != "canon", f["kind"] != "place", -f["design_value"]))
    L += ["## Stated geographical relationships"]
    L += [f"- {short(f['text'], 230)} [{tag(f)}] ({src(f)})" for f in geo[:6]] or ["- none stated in the sources"]
    L += ["- Anything not listed here (which city is where, what borders what) is NOT in the sources.", ""]

    # suggestions
    terr = box("canon", "terrain") or box("legends", "terrain")
    hits = sorted({v for k, v in GEN_TERRAIN.items() if k in terr.lower()})
    caps = [a for a in anchors if "capital" in a[3]]
    capital_hint = (max(caps, key=lambda a: a[0])[1] if caps else
                    "unnamed capital (the sources mention one): name it, mark the name invented"
                    if any(re.search(rf"\b{re.escape(planet)}\w* capital|capital city", f["text"]) for f in facts)
                    else "none in the sources: invent and say so")
    L += ["## SUGGESTION (inference, not lore)",
          f"- HOI4 terrain: {', '.join(hits) or '?'} (keyword match on '{terr[:60]}')",
          f"- capital state: {capital_hint}",
          "- other states: the anchors above, then regions named by the designer (label the names as invented)",
          "- battle sites: put the Clone Wars battles' VPs where the design needs fronts; sources give no spot", ""]

    # questions
    matter = ("cities", "interest", "terrain", "affiliation", "population", "government")
    conf = sorted({f["field"] for f in facts if f.get("conflict") and f["field"] in matter})
    L += ["## Questions that change the layout (ask the user once, together)"]
    for k in conf:
        L.append(f"- {k}: canon '{short(box('canon', k), 80)}' vs Legends '{short(box('legends', k), 80)}'")
    for g in gap_list:
        if g["status"] in ("open", "partial") and g["id"] in ("layout", "settlements", "landmarks", "clone_wars_control"):
            L.append(f"- [{g['status']}] {g['question']}")
    L.append("- More evidence: query facts.json by place / category (see the skill); dossier.md has the long version.")
    L += ["", "Sources:"] + [f"[{t}]: {u.replace(' ', '_').replace('(', '%28').replace(')', '%29')}" for t, u in refs.items()]
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")


# ---------------------------------------------------------------- run
def research(planet, refresh, gap_mode, max_images):
    fx = Fetcher(refresh)
    log(f"{planet}: research{' (refresh)' if refresh else ''}{' + gaps' if gap_mode else ''}")
    main = fx.pages([planet, f"{planet}/Legends"])
    if main[planet].get("missing") and main[f"{planet}/Legends"].get("missing"):
        if main[planet].get("unavailable"):
            sys.exit(f"FAILED: Wookieepedia API unavailable ({fx.last_error or 'failed recently'}); recorded in "
                     f"{os.path.relpath(fx.fail_path, ROOT)}, not retried for {RETRY_HOURS} h unless --refresh. "
                     "Nothing was written.")
        sys.exit(f"no Wookieepedia article '{planet}': check the spelling / capitalisation (titles are case-sensitive)")
    resolved = (main[planet]["title"] if not main[planet].get("missing")
                else main[f"{planet}/Legends"]["title"].removesuffix("/Legends"))
    if resolved != planet:                                                 # 'felucia' -> 'Felucia': one name everywhere
        log(f"  '{planet}' is '{resolved}' on Wookieepedia")
        canon_page, legends_page = main.values()
        planet = resolved
        main = {planet: canon_page, f"{planet}/Legends": legends_page}
    folder = os.path.join(OUT, slug(planet))
    state = jload(os.path.join(folder, "state.json"), {"searched": {}, "extra_pages": {}})
    facts, boxes = [], {}
    for t, p in main.items():
        if not p.get("missing"):
            boxes[t] = article_facts(facts, p)
    # the places the infoboxes name (cities first), each in its own continuity
    places = []
    for t, box in boxes.items():
        for role in ("cities", "interest"):
            places += [(l, role) for l in box.get(role, {}).get("links", [])]
    places = list(dict.fromkeys(places))[:2 * MAX_PLACES]
    # battles: the planet's battle pages (search), canon and Legends
    hits = fx.api(action="query", list="search", srsearch=f"Battle of {planet}", srlimit=20) or {}
    battles = [h["title"] for h in hits.get("query", {}).get("search", []) if planet.lower() in h["title"].lower()
               and "disambiguation" not in h["title"]][:MAX_BATTLES * 2]
    extra = state["extra_pages"]
    got = fx.pages([p for p, _ in places] + battles + list(extra))
    for p, role in places:
        if not got[p].get("missing"):
            place_facts(facts, got[p], role, planet)
    for b in battles:
        if not got[b].get("missing"):
            battle_facts(facts, got[b], planet)
    keywords = {f.get("place", "") for f in facts if f.get("place")}
    images = image_candidates(fx, planet, [k for k in keywords if k])
    if gap_mode:                                                           # targeted searches for open gaps, once each
        prior = gaps(planet, facts, images)
        for g in prior:
            if g["status"] in ("open", "partial"):
                for q in g["searches"]:
                    if q in state["searched"] and not refresh:
                        continue
                    r = fx.api(action="query", list="search", srsearch=q, srlimit=5) or {}
                    state["searched"][q] = now().isoformat()
                    for h in r.get("query", {}).get("search", []):
                        snippet = clean(re.sub(r"<[^>]+>", "", h.get("snippet", "")))
                        if (planet.lower() in (h["title"] + snippet).lower() and h["title"] not in extra
                                and h["title"] not in main and h["title"] not in got):
                            extra[h["title"]] = g["id"]
        new = fx.pages([t for t in extra if t not in got])
        got.update(new)
    for t, gid in extra.items():
        p = got.get(t)
        if p and not p.get("missing"):
            role = "interest"                                              # a search hit is not a known city
            if gid == "battles":
                battle_facts(facts, p, planet)
            else:
                place_facts(facts, p, role, planet)
    for f in facts:                                                        # remember which gap search found it
        if f["evidence"][0]["source"] in extra:
            f["found_by"] = extra[f["evidence"][0]["source"]]
    mark_conflicts(facts)
    img_note = download_images(fx, images, os.path.join(folder, "references"), max_images)
    if img_note:
        log("  " + img_note)
    gap_list = gaps(planet, facts, images)

    pages_used = {**main, **got}
    srcs = []
    for t, p in pages_used.items():
        used = any(e["source"] == p.get("title") for f in facts for e in f["evidence"])
        status = "ok" if not p.get("missing") else "unavailable" if p.get("unavailable") else "missing"
        if status == "ok" and not used:
            continue
        srcs.append(dict(id=f"wp:{p.get('title', t)}@{p.get('revid', '-')}", title=p.get("title", t),
                         url=WIKI + p.get("title", t).replace(" ", "_"), continuity=continuity(dict(p, title=p.get("title", t))),
                         revid=p.get("revid"), revision_time=p.get("timestamp"), status=status,
                         retrieved=now().strftime("%Y-%m-%d"), license=TEXT_LICENSE,
                         cache=f"_cache/api (revids={p.get('revid')})" if p.get("revid") else None))
    old = {s["id"]: s for s in jload(os.path.join(folder, "sources.json"), {}).get("sources", [])}
    for s in srcs:                                                         # keep the first retrieval date per revision
        if s["id"] in old:
            s["retrieved"] = old[s["id"]]["retrieved"]
    os.makedirs(folder, exist_ok=True)
    jsave(os.path.join(folder, "sources.json"), {"planet": planet, "sources": srcs})
    jsave(os.path.join(folder, "facts.json"), {
        "planet": planet, "generated": now().isoformat(), "schema": "fact: id, category, text, continuity "
        "(canon|legends, never merged), era (before-clone-wars|clone-wars|after-clone-wars|timeless|all-eras|out-of-universe|"
        "unspecified), confidence "
        "(high = cited infobox, medium = cited or infobox, low = uncited or hedged), kind (infobox|prose|place|battle), "
        "evidence [source, url, section, quote], conflict = infobox value differs between continuities, "
        "design_value (map-relevant words), review (fragment|narrative|weak-category|off-surface|not-in-clone-wars: "
        "doubtful, kept for review, ranked down)",
        "facts": facts, "gaps": gap_list})
    jsave(os.path.join(folder, "references", "index.json"), {"note": "licensing = the file page's licensing "
          "template; nothing here is cleared for redistribution", "images": images})
    write_dossier(os.path.join(folder, "dossier.md"), planet, facts, srcs, images, gap_list, img_note, max_images)
    write_brief(os.path.join(folder, "design_brief.md"), planet, facts, images, gap_list)
    write_gaps(os.path.join(folder, "research_gaps.md"), planet, gap_list, state["searched"])
    jsave(os.path.join(folder, "state.json"), state)
    size = os.path.getsize(os.path.join(folder, "dossier.md"))
    log(f"{len(facts)} facts ({sum(f['continuity'] == 'canon' for f in facts)} canon), {len(srcs)} sources, "
        f"{sum(1 for c in images if c.get('local'))}/{len(images)} images saved; dossier {size} bytes (~{size // 4} tokens)")
    log(f"requests {stats['api']}, cache hits {stats['api_cached']}, failed {stats['fail']}, skipped (failed recently) "
        f"{stats['skipped_failed']}, images new {stats['img_new']} / cached {stats['img_cached']}")
    log("gaps: " + ", ".join(f"{g['id']}={g['status']}" for g in gap_list))
    open(os.path.join(folder, "research.log"), "a", encoding="utf-8").write(f"{now():%Y-%m-%d %H:%M} " +
                                                                            " | ".join(log_lines) + "\n")
    return 1 if stats["fail"] and not facts else 0


def selftest():
    w = ("{{Top|can}}\n{{CelestialBody\n|name=X\n|terrain=[[Jungle]]s<ref name=\"a\">src</ref>\n|cities=*[[Akira]]\n"
         "*[[Kway Teow/Legends|Kway]] {{C|capital}}\n}}\n'''X''' is a [[planet]].<ref>r</ref> It had giant red "
         "[[fungus|fungi]] everywhere.\n==Appearances==\n*Skip me, a long enough line to be a sentence.\n")
    name, box = infobox(w, "CelestialBody")
    assert name == "CelestialBody" and box["terrain"]["text"] == "Jungles" and box["terrain"]["cited"]
    assert box["cities"]["links"] == ["Akira", "Kway Teow/Legends"] and "Kway (capital)" in box["cities"]["text"]
    secs = sections(w)
    assert [s for s, _ in secs] == ["Lead"] and "CelestialBody" not in secs[0][1]
    assert [t for t, _, _ in sentences(secs[0][1])] == ["It had giant red fungi everywhere."]   # 'X is a planet.' is too short
    facts = []
    a = add_fact(facts, {"title": "X"}, "prose", "biomes", "The jungle of X is full of giant red fungi trees.", "Lead", True, [])
    add_fact(facts, {"title": "X"}, "prose", "biomes", "The jungle of X is full of giant red fungi trees!", "Lead", True, [])
    add_fact(facts, {"title": "X/Legends"}, "prose", "biomes", "The jungle of X is full of giant red fungi trees.", "Lead", True, [])
    assert len(facts) == 2 and len(a["evidence"]) == 1 and {f["continuity"] for f in facts} == {"canon", "legends"}
    add_fact(facts, {"title": "X"}, "infobox", "infobox", "moons: 8", "Infobox", True, [], {"field": "moons"})
    add_fact(facts, {"title": "X/Legends"}, "infobox", "infobox", "moons: 2", "Infobox", True, [], {"field": "moons"})
    mark_conflicts(facts)
    assert sum(1 for f in facts if f.get("conflict")) == 2
    assert era("History > Clone Wars", "x") == "clone-wars" and categorize("a battle was fought", "Lead") == "battles"
    assert era("Lead", "built shortly after the end of the Clone Wars") == "after-clone-wars"
    assert continuity({"title": "Battle of X (Y)", "text": "{{Top|leg}}\n"}) == "legends"
    assert continuity({"title": "X", "text": "{{Top|notoc=1}}"}) == "canon"
    assert infobox("{{Interlang\n|de=X\n}}\n{{City\n|name=A\n}}")[0] == "City"
    assert era("History > Colonization and Republic Era", "In 60 BBY, a trial.") == "before-clone-wars"
    assert era("History > Under the Empire", "Separatist holdouts remained.") == "after-clone-wars"
    assert era("Lead", "Around 20 BBY it fell.") == "clone-wars" and era("Description", "A hot world.") == "timeless"
    assert clean("Felucia ( or /fʌ'lusiə/) was a world") == "Felucia was a world"
    assert infobox("{{City\n|cities=*[[Kway Teow]] {{C|[[Capital|capital]]}}\n}}")[1]["cities"]["links"] == ["Kway Teow"]
    g = add_fact([], {"title": "X"}, "prose", "visual", "He was horrified and saw blue light.", "Lead", True, [])
    assert {"narrative", "weak-category"} <= set(g["review"])
    print("selftest ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("planet", nargs="?", help="Wookieepedia article title, e.g. Felucia, 'Raxus Prime'")
    ap.add_argument("--refresh", action="store_true", help="re-check revisions and retry failed sources")
    ap.add_argument("--gaps", action="store_true", help="also run the follow-up searches of open gaps (once each)")
    ap.add_argument("--max-images", type=int, default=MAX_IMAGES, help=f"images to save (default {MAX_IMAGES})")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    elif not a.planet:
        ap.error("planet required")
    else:
        sys.exit(research(a.planet, a.refresh, a.gaps, a.max_images))
