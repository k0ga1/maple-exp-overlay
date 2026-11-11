import json,re,xml.etree.ElementTree as ET
W='/home/claude/hms/wz'
s=json.load(open('/home/claude/scripts/stage1.json'))
lvl={}
for mid in open('/home/claude/scripts/mobids.txt').read().split():
  try:
    r=ET.parse(f'{W}/Mob.wz/{int(mid):07d}.img.xml').getroot()
    info=r.find("imgdir[@name='info']")
    v={c.get('name'):c.get('value') for c in info}
    lvl[mid]=int(v.get('level',0))
  except Exception as e: pass
norm=lambda t:re.sub(r'[^a-z0-9]','',t.lower())
ours={}
for line in open('/home/claude/repo/assets/maps.txt',encoding='utf-8'):
  if '\t' in line:
    n,town=line.rstrip('\n').split('\t'); ours[norm(n)]=(n,town=='1')
out={};hit=0;by={}
for mid,m in s['maps'].items():
  k=norm(m['name'])
  if k in ours and not ours[k][1]:
    name=ours[k][0]
    mobs=[]
    for i,c in m['mobs']:
      nm=s['mobnames'].get(i)
      if nm and not nm.startswith('Strange ') and 0 < lvl.get(i,0) <= 120 and nm not in [x[0] for x in mobs]: mobs.append([nm,lvl[i]])
    mobs.sort(key=lambda x:x[1])
    if mobs:
      by.setdefault(name,[]).append((m['street'],mobs))
for name,v in by.items():
  street,mobs=v[0]
  if len(v)>1:   # same name in several places: keep only when all agree
    if any(x[1]!=mobs for x in v): continue
  out[name]={'region':street,'mobs':mobs}
tot=sum(1 for n,t in ours.values() if not t)
print(len(out),'of',tot,'hunting maps')
print(json.dumps(out.get('Tree Dungeon, Monkey Forest I') or [k for k in out if 'Monkey' in k]))
miss=[n for n,t in ours.values() if not t and n not in out]; print(len(miss), miss[:40])
json.dump(out,open('/home/claude/scripts/map_mobs.json','w'),ensure_ascii=False,indent=0)
