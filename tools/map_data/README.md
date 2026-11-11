# Map and item data

`assets/map_mobs.json` (monsters per map) and `assets/item_prices.json` (NPC sell prices and drops) are made from
[HeavenMS](https://github.com/ronancpl/HeavenMS)'s dump of the game's data files (old GMS: Classic World may differ).
Run in order, with a sparse clone of HeavenMS at `/home/claude/hms` (`wz/String.wz`, `wz/Map.wz/Map/Map0-2`, `wz/Mob.wz`,
`wz/Item.wz`, the equips in `wz/Character.wz` that drop, and `sql/db_drops.sql`): `mobs1.py`, `mobs2.py`, `items1.py`,
`items2.py`. The paths are written in the scripts; change them for your machine.
