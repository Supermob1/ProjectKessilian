"""Clone Wars reskin of the SW tech backgrounds: same size/fade(alpha)/grey tone as the Executor art,
picture swapped for our own loading-screen art. Originals kept as *_executor.dds in scratchpad."""
import os, shutil
from PIL import Image, ImageOps, ImageStat
M = r"F:\Documents\Paradox Interactive\Hearts of Iron IV\mod\ProjectKessilian"
S = os.path.dirname(os.path.abspath(__file__))
G, L = os.path.join(M, "gfx", "interface"), os.path.join(M, "gfx", "loadingscreens")
CROP = (340, 470, 1580, 1230)  # art window inside the loading-screen frame (1920x1440)
PICK = {"imperial_techtree_bg": "load_6", "supportweapons_techtree_bg": "load_dod", "swarmour_techtree_bg": "load_5",
        "swartillery_techtree_bg": "load_13", "imperial_armor_bg": "load_bba", "imperial_air_bg": "load_3"}
sheet = []
for bg, src in PICK.items():
    p = os.path.join(G, bg + ".dds")
    keep = os.path.join(S, bg + "_executor.dds")
    if not os.path.exists(keep):
        shutil.copy2(p, keep)
    old = Image.open(keep).convert("RGBA")
    a = old.getchannel("A")
    ref = ImageStat.Stat(old.convert("L"))  # their art: flat low alpha, full-contrast grey, edges fade to black
    art = Image.open(os.path.join(L, src + ".dds")).convert("RGB").crop(CROP)
    g = ImageOps.fit(art, old.size, Image.LANCZOS).convert("L")
    st = ImageStat.Stat(g)
    k = ref.stddev[0] / max(st.stddev[0], 1)
    g = g.point(lambda v: max(0, min(255, int((v - st.mean[0]) * k + ref.mean[0]))))
    w, h = old.size; f = 0.08
    import numpy as np
    xs = np.minimum(np.arange(w), np.arange(w)[::-1]) / (w * f); ys = np.minimum(np.arange(h), np.arange(h)[::-1]) / (h * f)
    fade = np.clip(np.minimum.outer(np.clip(ys, 0, 1), np.clip(xs, 0, 1)), 0, 1)
    a = Image.fromarray((np.asarray(a, dtype=float) * fade).astype("uint8"))  # feather into transparency
    new = Image.merge("RGBA", (g, g, g, a))
    new.save(p)
    assert Image.open(p).size == old.size
    t = Image.merge("RGBA", (g, g, g, Image.new("L", old.size, 255))); t.thumbnail((360, 360)); sheet.append(t)
W = sum(t.width for t in sheet); out = Image.new("RGBA", (W, max(t.height for t in sheet)), (40, 40, 40, 255)); x = 0
for t in sheet:
    out.paste(t, (x, 0), t); x += t.width
out.save(os.path.join(S, "bgs_cw.png"))
