import json, glob, os, xml.etree.ElementTree as ET
W = '/home/claude/hms/wz'
st = json.load(open('/home/claude/scripts/items_stage.json'))
names = {int(k): tuple(v) for k, v in st['names'].items()}
prices = {int(k): v for k, v in st['prices'].items()}
for f in glob.glob(f'{W}/Character.wz/*/*.img.xml'):
    iid = int(os.path.basename(f).split('.')[0])
    try:
        info = ET.parse(f).getroot().find("imgdir[@name='info']")
        v = {c.get('name'): c.get('value') for c in info}
        prices[iid] = int(float(v.get('price', 0)))
    except Exception:
        pass
s1 = json.load(open('/home/claude/scripts/stage1.json'))
mobs = {int(i) for m in s1['maps'].values() for i, _ in m['mobs']}
mobname = {int(k): v for k, v in s1['mobnames'].items()}
drops = {int(k): v for k, v in st['drops'].items()}
items, mob_drops = {}, {}
for mb in sorted(mobs):
    got = []
    for it, quest in drops.get(mb, []):
        if it not in names or it // 1000000 == 5:          # (cash items don't drop here)
            continue
        name, tab = names[it]
        key = f"{name}|{tab}"
        if key not in items:
            items[key] = {"name": name, "tab": tab, "price": prices.get(it, 0), "id": it, "quest": bool(quest)}
        if name not in got:
            got.append(name)
    if got and mob in mobname if False else got and mb in mobname:
        mob_drops.setdefault(mobname[mb], [])
        for n in got:
            if n not in mob_drops[mobname[mb]]:
                mob_drops[mobname[mb]].append(n)
# every potion and food too (they're in Use; picked up from the ground or shops)
for it, (name, tab) in names.items():
    if tab == 'Use' and 2000000 <= it < 2030000 and f"{name}|{tab}" not in items:
        items[f"{name}|{tab}"] = {"name": name, "tab": tab, "price": prices.get(it, 0), "id": it, "quest": False}
out = {"about": "NPC sell prices (what a shop pays you) and which monsters drop what. Made by tools/make_item_prices.py "
                 "from HeavenMS's dump of the game's data files (old GMS): MapleStory Classic World may differ for some items.",
       "items": sorted(([v["name"], v["tab"], v["price"], v["quest"]] for v in items.values()), key=lambda x: (x[1], x[0])),
       "mob_drops": mob_drops}
json.dump(out, open('/home/claude/repo/assets/item_prices.json', 'w'), ensure_ascii=False, separators=(",", ":"))
from collections import Counter
print(len(out["items"]), Counter(i[1] for i in out["items"]), len(mob_drops))
print([i for i in out["items"] if i[0] in ("Cursed Doll", "Lupin's Banana", "Banana", "Red Potion", "Orange Potion", "Meat", "Lemon")])
print(mob_drops.get("Lupin"))
print(os.path.getsize('/home/claude/repo/assets/item_prices.json'))
