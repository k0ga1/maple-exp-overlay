"""Reads what you pick up from the game's message corner (bottom right): "Tree Branch x1 earned. (Etc)".

The corner holds a stack of lines, the newest at the bottom; a new line pushes the others up a slot, and every line fades
over a few seconds. Pick-ups come in bursts (5 lines in a third of a second when you walk over a pile), so the corner
is looked at several times a second. Only when it changed are its lines read (Tesseract, all of them in one run), and the
new lines are found by lining the texts up with the last read: the lines that were there come back one or more slots
higher, and what's below them is new. A line that came back brighter than it was is new too (two identical lines in a
row, like "You received EXP (+10)" twice, look the same otherwise).

Item names are matched against the game's item list (assets/item_prices.json), the drops of the monsters on the map you
are on first: the reading is rough ("Tree Granch", "Green Mushroo..." cut short by the game), the match is not.
Positions are in design pixels (the game's 1024x768 UI) times the UI's scale, from the bottom right of the game window.
"""
import difflib
import json
import re
from collections import namedtuple

import cv2
import numpy as np

# Where the lines are: measured on 1920x1080 with the filter on (scale 1080/768), in design pixels.
BOTTOM_TOP = 162.1        # from the window's bottom to the top of the newest line
PITCH = 13.87             # from one line's top to the next
LINE_H = 10.0             # a line's height
RIGHT = 3.0               # from the window's right edge to the end of the lines (with a little room)
WIDTH = 330.0             # how far left a line can reach (the game cuts long names short)
SLOTS = 7                 # lines looked at (about 6 show; the 7th is mostly faded out)
PAD = 2.2                 # above and below a line, so the reading isn't cut

TABS = {"etc": "Etc", "use": "Use", "equip": "Equip", "setup": "Setup", "set-up": "Setup", "install": "Setup",
        "cash": "Cash"}
Pickup = namedtuple("Pickup", "name tab qty raw sure known", defaults=(True,))
# (sure: the name matched well, else a best guess; known: it's in the item list, so it has an NPC price)
CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,()+-':"


def scale_for(window_h):
    """The UI's scale for a game window this tall (the filtered UI follows the window's height)."""
    return window_h / 768.0


def band_box(window_w, window_h, scale=None):
    """(x, y, w, h) in the window of the band the lines are in."""
    s = scale or scale_for(window_h)
    top = window_h - (BOTTOM_TOP + PITCH * (SLOTS - 1) + PAD) * s
    bottom = window_h - (BOTTOM_TOP - LINE_H - PAD) * s
    x0 = window_w - (RIGHT + WIDTH) * s
    return int(max(0, x0)), int(max(0, top)), int(min(window_w, window_w - RIGHT * s + 2) - max(0, x0)), int(bottom - max(0, top))


def slot_rows(band_h, scale):
    """(y0, y1) of each slot inside the band, newest (bottom) first."""
    s = scale
    bottom_top = band_h - (LINE_H + PAD) * s - PAD * s          # the newest line's top inside the band
    rows = []
    for k in range(SLOTS):
        y = bottom_top - PITCH * s * k
        rows.append((int(round(y - PAD * s)), int(round(y + (LINE_H + PAD) * s))))
    return rows


def binarize(line):
    """The letters of a line as a mask: thin bright strokes (white top-hat), light and unsaturated."""
    g = cv2.cvtColor(line, cv2.COLOR_BGR2GRAY)
    th = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
    sat = cv2.cvtColor(line, cv2.COLOR_BGR2HSV)[..., 1]
    return ((th > 35) & (g > 150) & (sat < 70)).astype(np.uint8)


def span(mask, gap):
    """(left, right) of the right-aligned text in a line's mask: from its right end leftwards, until a gap wider than
    `gap` pixels (the scene beside it is left out). None when there's no text."""
    cols = mask.sum(axis=0) > 0
    xs = np.flatnonzero(cols)
    if not len(xs):
        return None
    right = xs.max()
    left, run = right, 0
    for x in range(right, -1, -1):
        if cols[x]:
            left, run = x, 0
        else:
            run += 1
            if run > gap:
                break
    return left, right


def ocr_picture(line, mask, sp):
    """A line made ready for Tesseract: its letters black on white, 4x bigger, with a margin."""
    m = mask[:, max(0, sp[0] - 2):sp[1] + 3] * 255
    up = cv2.resize(m.astype(np.uint8), None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    up = cv2.threshold(up, 100, 255, cv2.THRESH_BINARY)[1]
    up = cv2.copyMakeBorder(up, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=0)
    return 255 - up


def brightness(line, mask):
    """How bright a line's letters are (a new line is at its brightest, then fades): the mean grey under its mask."""
    if mask.sum() < 8:
        return 0.0
    g = cv2.cvtColor(line, cv2.COLOR_BGR2GRAY)
    return float(g[mask > 0].mean())


def norm(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


EARNED = re.compile(r"\b[ec]?[ao]?[ar]?[nmr]{1,2}[ei]?[edl]\b|earn|arned|eamed|earmed|eared")
TAB_RE = re.compile(r"\(\s*([a-z][a-z-]{1,6})\W*$")
QTY_RE = re.compile(r"\s[x×X*<«]\s?([0-9lIoOS]{1,4})\b")


def kind_of(text):
    """"item", "exp", "mesos" or None for a line as read."""
    low = text.lower()
    if "meso" in low and ("gain" in low or "ained" in low or "+" in low):
        return "mesos"
    if "exp" in low and ("receiv" in low or "eived" in low or "+" in low):
        return "exp"
    if TAB_RE.search(low.strip()) or "earn" in low or "arned" in low or "eamed" in low or "earmed" in low:
        return "item"
    return None


def parse(text):
    """(name as read, quantity, tab) of an "<item> x<n> earned. (<tab>)" line, or None for any other line. Lenient:
    the reading is rough, and a missing "x1" is a 1."""
    t = text.strip().replace("’", "'").replace("‘", "'")
    if kind_of(t) != "item":
        return None
    low = t.lower()
    tab = None
    m = TAB_RE.search(low)
    if m:
        read_tab, best = norm(m.group(1)), 0.0
        for key, value in TABS.items():
            r = difflib.SequenceMatcher(None, read_tab, norm(key)).ratio()
            if r > best:
                best, tab = r, value
        if best < 0.5:
            tab = None
    # the name: what's before " x<n>", else before the "earned" word
    qty, cut_at = 1, None
    q = QTY_RE.search(t)
    if q:
        digits = q.group(1).translate(str.maketrans("lIoOS", "11005"))
        if digits.isdigit() and 0 < int(digits) < 10000:
            qty = int(digits)
        cut_at = q.start()
    if cut_at is None:
        e = re.search(r"\s\S*(earn|arned|eamed|earmed|eared|amed)", low)
        cut_at = e.start() if e else None
    if cut_at is None:
        return None
    raw = t[:cut_at].rstrip()
    cut = bool(re.search(r"(\.\.|…|\.,|:\.|\.:)$", raw))           # (the game cut a long name short)
    name = re.sub(r"^[^A-Za-z]+", "", raw.strip(" .,'\"-_|*`~;:"))
    if len(name) < 3:
        return None
    return name + ("..." if cut else ""), qty, tab


class ItemNames:
    """The game's items (name, tab, NPC sell price) and which monster drops what, to turn a rough reading into an item."""

    def __init__(self, items, mob_drops):
        self.items = {}                                  # name -> (tab, price, quest)
        for name, tab, price, quest in items:
            self.items.setdefault(name, (tab, price, quest))
        self.mob_drops = mob_drops
        self._norm = {norm(n): n for n in self.items}

    @classmethod
    def load(cls, path):
        data = json.loads(open(path, encoding="utf-8").read())
        return cls(data.get("items", []), data.get("mob_drops", {}))

    def price(self, name):
        return (self.items.get(name) or (None, 0, False))[1]

    def candidates(self, mobs):
        """Item names the monsters `mobs` drop (plus every potion and food: they come from other places too)."""
        names = []
        for m in mobs or ():
            names += self.mob_drops.get(m, [])
        return list(dict.fromkeys(names))

    def match(self, read, tab, mobs=()):
        """(item name, score 0-1) for a name as read, or (None, 0). A name the game cut short ("Green Mushroo...") is
        matched on its start. The drops of the monsters on the map are tried first, and need less to match."""
        cut = bool(re.search(r"(\.\.|…|\.,|:\.|\.:)\s*$", read.rstrip())) or ".." in read
        key = norm(re.split(r"\.\.|…", read)[0] if cut else read)
        if len(key) < 3:
            return None, 0.0
        pools = [(self.candidates(mobs), 0.55), (list(self.items), 0.80)]
        for pool, need in pools:
            if tab:
                pool = [n for n in pool if self.items.get(n, (None,))[0] in (tab, None)] or pool
            best, score = None, 0.0
            for n in pool:
                nk = norm(n)
                target = nk[:len(key)] if cut and len(nk) > len(key) else nk
                r = difflib.SequenceMatcher(None, key, target).ratio()
                if r > score:
                    best, score = n, r
            if best and score >= (max(need, 0.8) if len(key) <= 5 else need):
                return best, score
        return None, 0.0


def strokes(line):
    """A line's thin bright strokes as a grey picture (white top-hat): the letters, whatever their fade, with most of
    the scene behind them gone."""
    g = cv2.cvtColor(line, cv2.COLOR_BGR2GRAY)
    return cv2.morphologyEx(g, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))).astype(np.float32)


def same_line(a, b, sp):
    """How alike two line pictures' strokes are over the text span `sp` of `a` (normalised correlation, a pixel or two
    of play): 1 the same, near 0 unrelated. A line fading out stays alike (the correlation doesn't mind the scale)."""
    x0, x1 = max(0, sp[0] - 1), sp[1] + 2
    t = a[2:-2, x0:x1] if a.shape[0] > 6 else a[:, x0:x1]
    src = b[:, max(0, x0 - 3):min(b.shape[1], x1 + 3)]
    if t.size == 0 or src.shape[0] < t.shape[0] or src.shape[1] < t.shape[1] or float(t.std()) < 1e-3:
        return 0.0
    return float(cv2.matchTemplate(src, t, cv2.TM_CCOEFF_NORMED).max())


def glow(line, mask):
    """How bright a line's letters still are: a new line starts at its brightest (about 200 of 255 in the strokes) and
    fades a little more each moment. The 80th percentile of the strokes under its mask, 0 for no text."""
    v = strokes(line)[mask > 0]
    return float(np.percentile(v, 80)) if v.size > 20 else 0.0


def same_text(a, b):
    """Two readings of what may be one line: the item names alike (a faded line reads worse), else the whole lines."""
    pa, pb = parse(a), parse(b)
    if pa and pb:
        return difflib.SequenceMatcher(None, norm(pa[0]), norm(pb[0])).ratio() >= 0.6
    if (pa is None) != (pb is None) and kind_of(a) and kind_of(b) and kind_of(a) != kind_of(b):
        return False
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio() >= 0.7


class LootFeed:
    """Follows the corner from look to look and says what was picked up since the last one."""

    FRESH = 175.0               # a new line's letters are at least this bright
    STILL = 0.95                # the newest line's picture this alike: nothing moved
    DIM = 120.0                 # a line this faded isn't read any more
    READS = 3                   # a new line is read up to this many times (the best reading wins)
    RISE = 12.0                 # a new line at the bottom is at least this much brighter than the line that was there

    def __init__(self, names, read_lines):
        self.names, self.read_lines = names, read_lines
        self.prev = None         # the last look: [(line, strokes, mask, span, glow)] newest first ([] = no lines)
        self.unknown = []        # item lines that matched no item: [(text as read)]
        self.read_count = 0      # lines sent to Tesseract (for health and tests)
        self.pending = []        # new lines still being read: {"slot", "reads"}
        self.texts = []          # the last reading of each of the last look's lines (None: not read)

    def _slots(self, band, scale):
        out = []
        gap = max(9, int(round(10 * scale)))
        for y0, y1 in slot_rows(band.shape[0], scale):
            line = band[max(0, y0):max(0, y1)]
            if line.shape[0] < 4:
                out.append(None)
                continue
            m = binarize(line)
            sp = span(m, gap)
            if sp is None or sp[1] - sp[0] < 25 * scale:
                out.append(None)
                continue
            out.append((line, strokes(line), m, sp, glow(line, m)))
        while out and out[-1] is None:
            out.pop()
        return out

    @staticmethod
    def _glows(lines):
        return [l[4] if l else 0.0 for l in lines]

    def _shift(self, cur):
        """How many lines at the bottom of `cur` are new. The newest line unmoved (its picture nearly the same): none.
        Else the shift that best explains the brightness: the new lines at the bottom fresh, the old ones back n
        slots higher and a little dimmer."""
        old = self.prev
        if not cur:
            return 0
        if not old:
            return sum(1 for g in self._glows(cur) if g >= self.FRESH) or 0
        if old[0] and cur[0] and same_line(old[0][1], cur[0][1], old[0][3]) >= self.STILL:
            return 0
        go, gc = self._glows(old), self._glows(cur)
        best, cost_best = 0, None
        for n in range(0, len(gc) + 1):
            if any(gc[k] < self.FRESH - 25 for k in range(n)):
                break                                      # (a new line is bright; the ones above it can't be new)
            pairs = [(go[j], gc[j + n]) for j in range(min(len(go), len(gc) - n)) if go[j] > 0 or gc[j + n] > 0]
            if pairs:
                drops = [a - b for a, b in pairs if a > 0 and b > 0]
                d = min(60.0, max(0.0, float(np.median(drops)))) if drops else 0.0
                cost = float(np.mean([(b - (a - d)) ** 2 if a > 0 and b > 0 else 900.0 for a, b in pairs]))
            else:
                cost = 0.0
            cost += 40.0 * n                               # (prefer fewer new lines when it's a tie)
            if n == 0 and gc[0] > go[0] + 20:
                cost += 5000.0                             # (the newest line got brighter: something new came)
            if cost_best is None or cost < cost_best:
                best, cost_best = n, cost
        return best

    def look(self, band, scale, mobs=()):
        """Feeds one picture of the band (band_box). Returns the Pickups that are settled since the last look: a new
        line is read at its arrival and again at the next looks while it's still bright (up to READS times), and the
        reading that matches an item best wins."""
        cur = self._slots(band, scale)
        old, old_texts = self.prev, self.texts
        n = self._shift(cur)
        if n and old and old[0] and cur and cur[0] and cur[0][4] <= old[0][4] - 3:
            n = 0                                          # (the bottom line got dimmer: it's the old one, fading on)
        if n and old and old[0] and cur and cur[0] and cur[0][4] < old[0][4] + self.RISE:
            # Not clearly a new, brighter line at the bottom (the camera moved, or the line just faded on): read the
            # bottom two. The same texts in the same places: nothing came in.
            check = [k for k in range(min(2, len(cur), len(old))) if cur[k] and old[k] and old_texts[k]]
            if check:
                texts = [t.strip() for t in self.read_lines([ocr_picture(cur[k][0], cur[k][2], cur[k][3]) for k in check])]
                self.read_count += len(check)
                if all(same_text(t, old_texts[k]) for k, t in zip(check, texts)):
                    n = 0
        self.prev = cur
        self.texts = ([None] * n + list(old_texts or []))[:len(cur)] + [None] * max(0, len(cur) - n - len(old_texts or []))
        for p in self.pending:
            p["slot"] += n
        for k in range(n):
            if k < len(cur) and cur[k]:
                self.pending.append({"slot": k, "reads": []})
        todo = [p for p in self.pending if p["slot"] < len(cur) and cur[p["slot"]] and cur[p["slot"]][4] >= self.DIM]
        if todo:
            pics = [ocr_picture(cur[p["slot"]][0], cur[p["slot"]][2], cur[p["slot"]][3]) for p in todo]
            texts = [t.strip() for t in self.read_lines(pics)]
            self.read_count += len(pics)
            for p, t in zip(todo, texts):
                p["reads"].append(t)
                if p["slot"] < len(self.texts):
                    self.texts[p["slot"]] = t
        got, keep = [], []
        for p in self.pending:
            line = cur[p["slot"]] if p["slot"] < len(cur) else None
            gone = line is None or line[4] < self.DIM
            kinds = [kind_of(t) for t in p["reads"]]
            settled = gone or len(p["reads"]) >= self.READS or (
                p["reads"] and kinds.count("item") == 0 and len(p["reads"]) >= 2) or (kinds.count("item") >= 1 and self._best(p, mobs)[1] >= 0.9)
            if not settled:
                keep.append(p)
                continue
            pick = self._settle(p, mobs)
            if pick:
                got.append(pick)
        self.pending = keep
        return got

    def _best(self, p, mobs):
        """The best (item name, score, quantity, tab, text) among a line's readings."""
        best = (None, 0.0, 1, None, "")
        for t in p["reads"]:
            parsed = parse(t)
            if not parsed:
                continue
            read, qty, tab = parsed
            name, score = self.names.match(read, tab, mobs)
            if score > best[1] or (best[0] is None and not best[4]):
                best = (name, score, qty, tab, t)
        return best

    def _settle(self, p, mobs):
        kinds = [kind_of(t) for t in p["reads"]]
        if not p["reads"] or kinds.count("item") == 0:
            return None
        if kinds.count("item") * 2 < len([k for k in kinds if k]):
            return None                                   # (mostly read as an EXP or mesos line)
        name, score, qty, tab, text = self._best(p, mobs)
        qtys = [parse(t)[1] for t in p["reads"] if parse(t)]
        if qtys:
            qty = max(set(qtys), key=qtys.count)
        if name:
            return Pickup(name, self.names.items[name][0], qty, text, score >= 0.75)
        self.unknown.append(text or p["reads"][0])
        # Not in the list (an item Classic World added, say): kept under the name it was read as, when two readings
        # agree on a clean name (never OCR noise), at no price.
        reads = [parse(t) for t in p["reads"]]
        clean = [r[0] for r in reads if r and re.fullmatch(r"[A-Za-z][A-Za-z' -]{2,30}", r[0])]
        for c in set(clean):
            if clean.count(c) >= 2:
                tabs = [r[2] for r in reads if r and r[0] == c and r[2]]
                return Pickup(c.strip().title(), max(set(tabs), key=tabs.count) if tabs else None, qty, text, False, False)
        return None
