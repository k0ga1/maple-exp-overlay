"""Checks of the loot reader's text side (loot_reader.py): turning rough readings of "<item> x1 earned. (Etc)" lines
into items. The picture side was checked on a recording of real play (Field South of Ellinia, 1920x1080, filter on)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import loot_reader as lr  # noqa: E402

failed = 0


def check(what, ok):
    global failed
    print(("PASS " if ok else "FAIL ") + what)
    failed += not ok


check("a clean item line", lr.parse("Tree Branch x1 earned. (Etc)") == ("Tree Branch", 1, "Etc"))
check("a quantity", lr.parse("Arrows for Bows x21 earned. (Use)")[1] == 21)
check("no 'x1' read: one", lr.parse("Red Potion eamed. (Use)") == ("Red Potion", 1, "Use"))
check("a name the game cut short keeps its dots", lr.parse("Green Mushroo... x1 earned. (Etc)")[0] == "Green Mushroo...")
check("EXP and mesos lines aren't items", lr.parse("You received EXP (+10)") is None
      and lr.parse("You have gained mesos (+33)") is None)
names = lr.ItemNames.load(Path(__file__).resolve().parent.parent / "assets" / "item_prices.json")
mobs = ["Stump", "Slime", "Green Mushroom"]
check("a rough reading matches the map's drop", names.match("T-8e Brarth", "Etc", mobs)[0] == "Tree Branch")
check("a cut name matches on its start", names.match("Green Mushroo...", "Etc", mobs)[0] == "Green Mushroom Cap")
check("a short unknown name doesn't take a look-alike", names.match("Leaf", "Etc", mobs)[0] is None)
check("NPC prices are there", names.price("Red Potion") > 0)
print(f"\n{failed} FAILED" if failed else "\nALL PASSED")
sys.exit(1 if failed else 0)
