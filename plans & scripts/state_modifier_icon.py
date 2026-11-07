"""One generic 32x32 state-modifier icon (landmarks, Felucia): a square plate with a building in front.
python -B state_modifier_icon.py  ->  gfx/interface/state_modifiers/HOD_landmark.dds (+ preview png in scratch)"""
import os
from PIL import Image, ImageDraw, ImageFilter

S = 8  # supersample
N = 32 * S
OUT = os.path.join(os.path.dirname(__file__), "..", "gfx", "interface", "state_modifiers", "HOD_landmark.dds")

def r(*v): return [c * S for c in v]

def icon():
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # square plate: navy fill, steel frame, cyan inner line (house UI colours)
    d.rectangle(r(3, 2, 28, 25), fill=(0, 88, 137, 255))
    d.rectangle(r(4, 3, 27, 24), fill=(0, 12, 34, 255))
    d.rectangle(r(5, 4, 26, 23), outline=(0, 175, 250, 255), width=S // 2)
    # building silhouette in front, standing on the plate's bottom edge and spilling past it
    sh = Image.new("RGBA", (N, N), (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
    body = [r(9, 13, 23, 30), r(12, 9, 20, 13), r(14.5, 5, 17.5, 9), r(6, 20, 26, 30)]
    for b in body: sd.rectangle(b, fill=(0, 0, 0, 200))
    sh = sh.transform(sh.size, Image.AFFINE, (1, 0, -S, 0, 1, -S)).filter(ImageFilter.GaussianBlur(S))
    im.alpha_composite(sh)
    for b, col in zip(body, [(178, 186, 196), (198, 206, 214), (214, 220, 228), (150, 158, 170)]):
        d.rectangle(b, fill=col + (255,), outline=(40, 46, 56, 255), width=S // 2)
    # windows / door: dark cut lines so it reads at 32px
    for y in (16, 19):
        for x in (11, 15, 19):
            d.rectangle(r(x, y, x + 2, y + 1.5), fill=(40, 46, 56, 255))
    d.rectangle(r(14.5, 25, 17.5, 30), fill=(40, 46, 56, 255))
    d.rectangle(r(15.5, 6.5, 16.5, 8), fill=(240, 192, 32, 255))  # gold beacon
    return im.resize((32, 32), Image.LANCZOS)

if __name__ == "__main__":
    im = icon()
    assert im.size == (32, 32) and im.getpixel((16, 0))[3] == 0  # vanilla state-modifier size, transparent margin
    im.save(OUT)
    im.resize((256, 256), Image.NEAREST).save(os.path.join(os.environ.get("TEMP", "."), "hod_landmark_preview.png"))
    print("wrote", os.path.normpath(OUT))
