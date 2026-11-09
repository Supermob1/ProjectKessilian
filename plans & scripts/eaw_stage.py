"""Stage vanilla Empire at War / Forces of Corruption .alo models with the textures they use, for alo_to_glb.py:
    python -I -B "plans & scripts/eaw_stage.py" OUTDIR NAME [NAME ...]      (NAME = model stem, e.g. NB_BACTATANK)
-> OUTDIR/MODELS/NAME.ALO + OUTDIR/TEXTURES/*.dds (texture names are read out of the .alo's strings)."""
import os, re, struct, sys
EAW = "F:/SteamLibrary/steamapps/common/Star Wars Empire at War/"
MEGS = [EAW + "corruption/Data/", EAW + "GameData/Data/"]          # FoC first: it overrides the base game


def entries(p):
    f = open(p, "rb"); nn, nf = struct.unpack("<2I", f.read(8))
    names = []
    for _ in range(nn):
        (l,) = struct.unpack("<H", f.read(2)); names.append(f.read(l).decode("latin-1"))
    for _ in range(nf):
        crc, idx, size, start, ni = struct.unpack("<5I", f.read(20)); yield names[ni].upper(), p, start, size


INDEX = {}
for d in MEGS:
    for meg in ("models.meg", "textures.meg"):
        if os.path.exists(d + meg):
            for n, p, s, z in entries(d + meg):
                INDEX.setdefault(os.path.basename(n.replace("\\", "/")), (p, s, z))


def read(name):
    p, s, z = INDEX[name.upper()]
    f = open(p, "rb"); f.seek(s); return f.read(z)


out = sys.argv[1]
os.makedirs(out + "/MODELS", exist_ok=True); os.makedirs(out + "/TEXTURES", exist_ok=True)
for stem in sys.argv[2:]:
    alo = read(stem + ".ALO")
    open(f"{out}/MODELS/{stem}.ALO", "wb").write(alo)
    tex = {t.decode("latin-1").upper() for t in re.findall(rb"[\w\-]+\.(?:tga|dds)", alo, re.I)}
    got = []
    for t in tex:
        dds = os.path.splitext(t)[0] + ".DDS"
        if dds in INDEX:
            open(f"{out}/TEXTURES/{dds.lower()}", "wb").write(read(dds)); got.append(dds)
    print(stem, len(alo), "bytes, textures:", got)
