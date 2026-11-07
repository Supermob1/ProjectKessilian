"""Write generator-owned lines straight into history files (instead of on_startup on_actions).
Every injected line ends with '# HOD:<marker>' so a rerun replaces exactly its own lines."""
import glob, os, re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _rw(path, fn):
    raw = open(path, "rb").read()
    bom, t = raw.startswith(b"\xef\xbb\xbf"), raw.decode("utf-8-sig")
    crlf = "\r\n" in t
    new = fn(t.replace("\r\n", "\n"))
    if new != t.replace("\r\n", "\n"):
        open(path, "wb").write((b"\xef\xbb\xbf" if bom else b"") + (new.replace("\n", "\r\n") if crlf else new).encode("utf-8"))


def _strip(t, marker):
    return re.sub(r"\n[^\n]*# HOD:%s[ \t]*(?=\n)" % re.escape(marker), "", t)


def state_file(sid):
    f = glob.glob(os.path.join(ROOT, "history", "states", f"{sid}-*.txt"))
    assert len(f) == 1, f"state {sid}: {f}"
    return f[0]


def country_file(tag):
    f = glob.glob(os.path.join(ROOT, "history", "countries", f"{tag} - *.txt"))
    assert len(f) == 1, f"tag {tag}: {f}"
    return f[0]


def clear(marker, kind):
    """drop every line with this marker from all state ('states') or country ('countries') histories"""
    for p in glob.glob(os.path.join(ROOT, "history", kind, "*.txt")):
        _rw(p, lambda t: _strip(t, marker))


def set_state(sid, marker, lines):
    """put one-line effects at the top of the state's history = { } block"""
    def fn(t):
        t = _strip(t, marker)
        m = re.search(r"\n([ \t]*)history\s*=\s*\{[^\n]*", t)
        assert m, f"state {sid} has no history block"
        ind = m.group(1) + "\t"
        return t[:m.end()] + "".join(f"\n{ind}{L}\t# HOD:{marker}" for L in lines) + t[m.end():]
    _rw(state_file(sid), fn)


def set_country(tag, marker, lines):
    """append one-line top-level effects to the country's history (they run at game start)"""
    def fn(t):
        t = _strip(t, marker).rstrip("\n")
        return t + "".join(f"\n{L}\t# HOD:{marker}" for L in lines) + "\n"
    _rw(country_file(tag), fn)


if __name__ == "__main__":  # self-check on a temp copy
    import shutil, tempfile
    d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "history", "states"))
    p = os.path.join(d, "history", "states", "7-Test - A.txt")
    open(p, "w").write("state = {\n\tid = 7\n\thistory = {\n\t\towner = REP\n\t}\n}\n")
    ROOT = d
    set_state(7, "t", ["add_dynamic_modifier = { modifier = X }"]); set_state(7, "t", ["add_dynamic_modifier = { modifier = Y }"])
    s = open(p).read(); assert s.count("# HOD:t") == 1 and "modifier = Y" in s and s.index("modifier = Y") < s.index("owner"), s
    clear("t", "states"); assert "HOD:t" not in open(p).read()
    shutil.rmtree(d); print("ok")
