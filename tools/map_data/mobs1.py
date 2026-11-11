import re,glob,json,os,xml.etree.ElementTree as ET
W='/home/claude/hms/wz'
names={}
for d in ET.parse(f'{W}/String.wz/Map.img.xml').getroot():
  for m in d:
    s={c.get('name'):c.get('value') for c in m}
    names[m.get('name').lstrip('0')]=(s.get('streetName',''),s.get('mapName',''))
mob={d.get('name').lstrip('0'):{c.get('name'):c.get('value') for c in d}.get('name') for d in ET.parse(f'{W}/String.wz/Mob.img.xml').getroot()}
maps={}
for f in glob.glob(f'{W}/Map.wz/Map/Map[012]/*.img.xml'):
  mid=os.path.basename(f).split('.')[0].lstrip('0')
  try: r=ET.parse(f).getroot()
  except Exception: continue
  life=r.find("imgdir[@name='life']")
  if life is None: continue
  ids=[]
  for e in life:
    s={c.get('name'):c.get('value') for c in e}
    if s.get('type')=='m': ids.append(s['id'].lstrip('0'))
  if ids and mid in names:
    from collections import Counter
    maps[mid]={'street':names[mid][0],'name':names[mid][1],'mobs':Counter(ids).most_common()}
json.dump({'maps':maps,'mobnames':mob},open('/home/claude/scripts/stage1.json','w'))
allm=sorted({i for m in maps.values() for i,_ in m['mobs']})
print(len(maps),len(allm)); open('/home/claude/scripts/mobids.txt','w').write('\n'.join(allm))
