import re, json, glob, os, xml.etree.ElementTree as ET
W = '/home/claude/hms/wz'
def strings(f, nested=False):
    out = {}
    root = ET.parse(f'{W}/String.wz/{f}').getroot()
    def walk(node):
        for d in node:
            if d.tag != 'imgdir': continue
            vals = {c.get('name'): c.get('value') for c in d if c.tag == 'string'}
            if 'name' in vals and d.get('name').isdigit():
                out[int(d.get('name'))] = vals['name']
            else:
                walk(d)
    walk(root)
    return out
names = {}
for f, tab in (('Consume.img.xml', 'Use'), ('Etc.img.xml', 'Etc'), ('Ins.img.xml', 'Setup'), ('Eqp.img.xml', 'Equip')):
    for i, n in strings(f).items():
        names[i] = (n, tab)
prices = {}
for f in glob.glob(f'{W}/Item.wz/*/*.img.xml'):
    root = ET.parse(f).getroot()
    for item in root:
        if not item.get('name', '').isdigit(): continue
        info = item.find("imgdir[@name='info']")
        if info is None: continue
        v = {c.get('name'): c.get('value') for c in info}
        try: prices[int(item.get('name'))] = int(float(v.get('price', 0)))
        except ValueError: pass
# drops
drops, table = {}, None
for line in open('/home/claude/hms/sql/db_drops.sql', encoding='utf-8', errors='ignore'):
    m = re.search(r'INSERT (?:IGNORE )?INTO `?(\w+)`?', line)
    if m: table = m.group(1)
    if table not in ('drop_data', 'temp_data'): continue
    for t in re.findall(r'\((\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', line):
        mob, item, lo, hi, quest, chance = map(int, t)
        drops.setdefault(mob, []).append((item, quest))
json.dump({'names': {str(k): v for k, v in names.items()}, 'prices': {str(k): v for k, v in prices.items()},
           'drops': {str(k): v for k, v in drops.items()}}, open('/home/claude/scripts/items_stage.json', 'w'))
print(len(names), len(prices), len(drops))
# equips that drop from mobs on our maps
s1 = json.load(open('/home/claude/scripts/stage1.json'))
mobs = {int(i) for m in s1['maps'].values() for i, _ in m['mobs']}
eq = sorted({it for mb in mobs for it, q in drops.get(mb, []) if it // 1000000 == 1})
print('mobs', len(mobs), 'equips', len(eq))
open('/home/claude/scripts/equip_ids.txt', 'w').write('\n'.join(map(str, eq)))
