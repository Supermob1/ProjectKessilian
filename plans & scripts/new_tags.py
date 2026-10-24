"""New country tags for the neutral worlds of the new Clone Wars planets (the user, 2026-10-24: "neutral worlds are their own
tags"), made like UTA (Utapau): the tag line, common/countries, colours, history (capital = the planet's first state),
the leader (canon names only; the rest get the game's generated leaders), localisation for every ideology, flags and a
home-guard division in faction_templates.py. Run from the mod root, once (refuses a tag that exists):
    python -B "WIPGFX/plans & scripts/new_tags.py"     then python -B "WIPGFX/plans & scripts/faction_templates.py"
"""
import glob, os, re
from PIL import Image, ImageDraw

IDEOLOGIES = ["akaanadocrat", "unitist", "corist", "distributionist", "corporate_consortium", "trade_democrat", "ruusanist",
              "inclusivist", "force_magocracy"]
# tag: planet, file name, DEF, ADJ, colour, ruling party, popularities, leader (id, name, subtype, desc) or None,
#      flag (field, accent, emblem), guard division (name, numbered name)
TAGS = {
    "MRD": ("Maridun", "the Lurmen of Maridun", "Maridunian", (110, 150, 70), "distributionist",
            {"distributionist": 80, "inclusivist": 20},
            ("tee_watt_kaa", "Tee Watt Kaa", "symbiotist_subtype",
             "Chief of the Lurmen village on Maridun's plains. The Lurmen fled the war once already and will not take up "
             "arms in it, whatever either side drops on their fields."),
            ((70, 110, 50), (230, 200, 90), "sun"), ("Lurmen Village Watch", "%dth Lurmen Watch")),
    "ABA": ("Abafar", "the Abafar Rhydonium Concerns", "Abafarian", (228, 226, 214), "corporate_consortium",
            {"corporate_consortium": 70, "trade_democrat": 30}, None,
            ((230, 228, 218), (90, 90, 96), "drop"), ("Pons Ora Militia", "%dth Pons Ora Militia")),
    "ALE": ("Aleen", "the Kingdom of Aleen", "Aleena", (176, 120, 186), "unitist",
            {"unitist": 70, "inclusivist": 30}, None,
            ((120, 70, 140), (240, 210, 120), "crown"), ("Aleena Royal Guard", "%dth Aleena Guard")),
    "BDT": ("Bardotta", "the Queendom of Bardotta", "Bardottan", (150, 110, 200), "force_magocracy",
            {"force_magocracy": 60, "inclusivist": 40},
            ("julia", "Queen Julia", "light_side_subtype",
             "Queen of Bardotta. Her people trust the Dagoyan Masters' spiritual way over the Jedi Order's, and keep their "
             "world apart from both the Republic and the Confederacy."),
            ((90, 60, 140), (230, 220, 250), "ring"), ("Bardottan Guard", "%dth Bardottan Guard")),
    "KIR": ("Kiros", "the Kiros Colony", "Kirosian", (220, 120, 70), "inclusivist",
            {"inclusivist": 80, "trade_democrat": 20},
            ("roshti", "Governor Roshti", "inclusivist_subtype",
             "Governor of the Togruta colony on Kiros. The colony declared itself neutral and peaceful; its art and its "
             "people are known across the sector."),
            ((200, 90, 50), (245, 240, 230), "horns"), ("Kiros Colony Guard", "%dth Kiros Guard")),
    "LTM": ("Lotho Minor", "the Lotho Minor Junklands", "Lothan", (150, 120, 80), "distributionist",
            {"distributionist": 60, "corist": 40}, None,
            ((110, 90, 60), (230, 130, 40), "gear"), ("Junkyard Scavengers", "%dth Scavenger Band")),
    "CLC": ("Carlac", "the Ming Po of Carlac", "Carlacian", (190, 220, 240), "distributionist",
            {"distributionist": 80, "inclusivist": 20}, None,
            ((200, 225, 240), (60, 90, 140), "flake"), ("Ming Po Hunters", "%dth Ming Po Hunters")),
    "RAT": ("Rattatak", "the Warlords of Rattatak", "Rattataki", (140, 60, 60), "akaanadocrat",
            {"akaanadocrat": 80, "corist": 20}, None,
            ((50, 30, 30), (200, 60, 50), "skull"), ("Rattataki Warband", "%dth Rattataki Warband")),
    "NEL": ("Nelvaan", "the Nelvaanian Tribes", "Nelvaanian", (100, 150, 190), "distributionist",
            {"distributionist": 90, "inclusivist": 10}, None,
            ((50, 90, 130), (220, 230, 240), "horns"), ("Nelvaanian Warriors", "%dth Nelvaanian Warriors")),
}


def state_of(planet):
    f = glob.glob(f"history/states/*-{planet}.txt") + glob.glob(f"history/states/*-{planet} - *.txt")
    return min(int(os.path.basename(x).split("-")[0]) for x in f)


def flag(tag, field, accent, emblem):
    K = 8
    w, h = 82 * K, 52 * K
    im = Image.new("RGBA", (w, h), field + (255,))
    d = ImageDraw.Draw(im)
    cx, cy, s = w / 2, h / 2, 16 * K
    A = accent + (255,)
    d.rectangle([0, h - 6 * K, w, h], fill=A)
    if emblem == "sun":
        for i in range(12):
            import math
            a = math.tau * i / 12
            d.polygon([(cx + s * 0.6 * math.cos(a - 0.15), cy + s * 0.6 * math.sin(a - 0.15)),
                       (cx + s * 1.1 * math.cos(a), cy + s * 1.1 * math.sin(a)),
                       (cx + s * 0.6 * math.cos(a + 0.15), cy + s * 0.6 * math.sin(a + 0.15))], fill=A)
        d.ellipse([cx - s * 0.6, cy - s * 0.6, cx + s * 0.6, cy + s * 0.6], fill=A)
    elif emblem == "drop":
        d.polygon([(cx, cy - s), (cx + s * 0.6, cy + s * 0.2), (cx, cy + s * 0.8), (cx - s * 0.6, cy + s * 0.2)], fill=A)
    elif emblem == "crown":
        d.polygon([(cx - s, cy + s * 0.5), (cx - s, cy - s * 0.4), (cx - s * 0.5, cy), (cx, cy - s * 0.7), (cx + s * 0.5, cy),
                   (cx + s, cy - s * 0.4), (cx + s, cy + s * 0.5)], fill=A)
    elif emblem == "ring":
        d.ellipse([cx - s, cy - s, cx + s, cy + s], outline=A, width=4 * K)
        d.ellipse([cx - s * 0.25, cy - s * 0.25, cx + s * 0.25, cy + s * 0.25], fill=A)
    elif emblem == "horns":
        d.polygon([(cx - s * 0.9, cy + s * 0.7), (cx - s * 0.5, cy - s), (cx - s * 0.2, cy + s * 0.7)], fill=A)
        d.polygon([(cx + s * 0.9, cy + s * 0.7), (cx + s * 0.5, cy - s), (cx + s * 0.2, cy + s * 0.7)], fill=A)
    elif emblem == "gear":
        d.rectangle([cx - s * 0.9, cy - s * 0.2, cx + s * 0.9, cy + s * 0.2], fill=A)
        d.rectangle([cx - s * 0.2, cy - s * 0.9, cx + s * 0.2, cy + s * 0.9], fill=A)
        d.ellipse([cx - s * 0.6, cy - s * 0.6, cx + s * 0.6, cy + s * 0.6], fill=A)
        d.ellipse([cx - s * 0.25, cy - s * 0.25, cx + s * 0.25, cy + s * 0.25], fill=field + (255,))
    elif emblem == "flake":
        for dx, dy in ((1, 0), (0.5, 0.87), (0.5, -0.87)):
            d.line([cx - s * dx, cy - s * dy, cx + s * dx, cy + s * dy], fill=A, width=3 * K)
    elif emblem == "skull":
        d.ellipse([cx - s * 0.7, cy - s * 0.9, cx + s * 0.7, cy + s * 0.4], fill=A)
        d.rectangle([cx - s * 0.4, cy, cx + s * 0.4, cy + s * 0.8], fill=A)
        for ex in (-0.3, 0.3):
            d.ellipse([cx + (ex - 0.17) * s, cy - s * 0.4, cx + (ex + 0.17) * s, cy - s * 0.06], fill=field + (255,))
    for size, path in (((82, 52), f"gfx/flags/{tag}.tga"), ((41, 26), f"gfx/flags/medium/{tag}.tga"),
                       ((10, 7), f"gfx/flags/small/{tag}.tga")):
        im.resize(size, Image.LANCZOS).save(path)


def main():
    tags_file = "common/country_tags/HOD_countries.txt"
    tags_txt = open(tags_file, encoding="utf-8").read()
    for tag in TAGS:
        assert not re.search(rf"(?m)^{tag}\s*=", tags_txt), f"{tag} exists"
    template = open("history/countries/UTA - Utapau.txt", encoding="utf-8-sig").read()
    colors = open("common/countries/colors.txt", encoding="utf-8").read().rstrip("\n") + "\n"
    ft = "WIPGFX/plans & scripts/faction_templates.py"
    fts = open(ft, encoding="utf-8").read()
    for tag, (planet, DEF, ADJ, col, party, pops, leader, (field, accent, emblem), (guard, guard_n)) in TAGS.items():
        cap = state_of(planet)
        tags_txt = tags_txt.rstrip("\n") + f'\n{tag} = "countries/{planet}.txt"   # HOD: {planet} (new_tags.py; the user, 2026-10-24)\n'
        rgb = " ".join(map(str, col))
        open(f"common/countries/{planet}.txt", "w", encoding="utf-8", newline="\n").write(
            f"graphical_culture = western_european_gfx\ngraphical_culture_2d = western_european_2d\n\ncolor = rgb {{ {rgb} }}\n")
        colors += f"{tag} = {{\n\tcolor = rgb {{ {rgb} }}\n\tcolor_ui = rgb {{ {rgb} }}\n}}\n"
        h = template.replace("capital = 56", f"capital = {cap}").replace('oob = "HOD_UTA"', f'oob = "HOD_{tag}"')
        h = h.replace("producer = UTA", f"producer = {tag}")
        h = h.replace("recruit_character = UTA_tion_medon", f"recruit_character = {tag}_{leader[0]}" if leader else "")
        h = re.sub(r"set_popularities = \{.*?\n\}", "set_popularities = {\n" + "".join(
            f"\t{i} = {pops.get(i, 0)}\n" for i in IDEOLOGIES) + "}", h, flags=re.S)
        h = h.replace("ruling_party = trade_democrat", f"ruling_party = {party}")
        assert "UTA" not in h, tag
        open(f"history/countries/{tag} - {planet}.txt", "w", encoding="utf-8-sig", newline="\n").write(h)
        L = ["l_english:", f" # HOD: {planet} (new_tags.py; the user, 2026-10-24)", f' {tag}:0 "{planet}"',
             f' {tag}_DEF:0 "{DEF}"', f' {tag}_ADJ:0 "{ADJ}"']
        if leader:
            cid, name, sub, desc = leader
            open(f"common/characters/{tag}.txt", "w", encoding="utf-8", newline="\n").write(
                f'characters={{\n\t{tag}_{cid}={{\n\t\tname="{name}"\n\t\tcountry_leader={{\n\t\t\tdesc="{tag}_{cid}_desc"\n'
                f"\t\t\tideology={sub}\n\t\t\ttraits={{ }}\n\t\t\tid=-1\n\t\t}}\n\t}}\n}}\n")
            L.append(f' {tag}_{cid}_desc:0 "{desc}"')
        for i in IDEOLOGIES:
            L += [f' {tag}_{i}:0 "{planet}"', f' {tag}_{i}_DEF:0 "{DEF}"', f' {tag}_{i}_ADJ:0 "{ADJ}"']
        open(f"localisation/english/HOD_{tag}_l_english.yml", "w", encoding="utf-8-sig", newline="\n").write("\n".join(L) + "\n")
        flag(tag, field, accent, emblem)
        # a home-guard division (faction_templates.py writes the template, the names and the units)
        for a, b in ((f'    "UTA": {{"Utapaun Guard": T("UTA_INF_01", [[(I, 3)], [(I, 3)]], ["recon", "engineer"])}},',
                      f'    "{tag}": {{"{guard}": T("{tag}_INF_01", [[(I, 2)], [(I, 2)]], ["recon"])}},'),
                     (f'    "UTA": {{"UTA_INF_01": ("Utapaun Guard", "%dth Utapaun Guard", ["Pau City Guard", "Dactillion Riders"])}},',
                      f'    "{tag}": {{"{tag}_INF_01": ("{guard}", "{guard_n}", [])}},'),
                     ('    "UTA": ("history/units/HOD_UTA.txt", {"Utapau": [("Utapaun Guard", 2)]}),',
                      f'    "{tag}": ("history/units/HOD_{tag}.txt", {{"{planet}": [("{guard}", 1)]}}),')):
            assert fts.count(a) == 1, a
            fts = fts.replace(a, a + "\n" + b)
        print(f"{tag} {planet}: capital {cap}, {party}" + (f", {leader[1]}" if leader else ""))
    open(tags_file, "w", encoding="utf-8", newline="").write(tags_txt)
    open("common/countries/colors.txt", "w", encoding="utf-8", newline="").write(colors)
    open(ft, "w", encoding="utf-8", newline="").write(fts)


if __name__ == "__main__":
    main()
