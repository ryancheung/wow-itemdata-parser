import csv
import json

# Core bonding enum, for auto updating of bonding type?
BIND_TYPES = {
    "NO_BIND"                                     : 0,
    "BIND_WHEN_PICKED_UP"                         : 1,
    "BIND_WHEN_EQUIPPED"                          : 2,
    "BIND_WHEN_USE"                               : 3,
    "BIND_QUEST_ITEM"                             : 4,
}

NAME_TO_ID_HASH = {}
with open("item_db.csv", "rb") as f:
    # row is (id, itemlevel, name)
    for row in csv.reader(f):
        NAME_TO_ID_HASH[row[2]] = int(row[0])

def ItemNameToID(name):
    # go through item list, find name, return ID. Exact match for now
    if name is None:
        return -1

    if name in NAME_TO_ID_HASH:
        return NAME_TO_ID_HASH[name]

    return -1

class ItemVersion(dict):
    def __init__(self, *args, **kwargs):
        super(ItemVersion, self).__init__(*args, **kwargs)

    def __hash__(self):
        return id(json.dumps(self.hash_safe(), sort_keys = True))

    def hash_safe(self):
        # Strip unnecessary keys from the dict for hashing so we can avoid
        # duplicates
        copy = self.copy()
        del copy["flavour"]

        return copy

    @classmethod
    def new(cls):
        return ItemVersion({
                # Fill basic item values
                "name": None,
                "quality": None,
                "slot": None,
                "armor": 0,
                "bonding": BIND_TYPES["NO_BIND"],
                "itemType": None,
                "mindamage": 0,
                "maxdamage": 0,
                "speed": 0,
                "requiredlevel": 0,
                "stamina": 0,
                "strength": 0,
                "spirit": 0,
                "intellect": 0,
                "agility": 0,
                "resistances": {
                    "arcane": 0,
                    "fire": 0,
                    "frost": 0,
                    "nature": 0,
                    "shadow": 0,
                    "holy": 0
                },
                "effects": [],
                "flavour": None,
                "quest": False,
                "trade_good": False
            })

class ItemSpell(dict):
    def __init__(self, spellId, tooltip, *args, **kwargs):
        super(ItemSpell, self).__init__(*args, **kwargs)

        self["spellId"] = spellId
        self["tooltip"] = tooltip

class ItemStore(dict):
    def __init__(self, *args, **kwargs):
        super(ItemStore, self).__init__(*args, **kwargs)

    def add_item(self, item_id, patchLevel, item):
        if item_id not in self:
            self[item_id] = {}

        if patchLevel not in self[item_id]:
            self[item_id][patchLevel] = set()

        self[item_id][patchLevel].add(item)

    def merge_into(self, base):
        """
        Merges data in this store into the base store, without overwriting anything
        """
        for item_id in self:
            # speedup, just assign full value if not existing
            if item_id not in base:
                base[item_id] = self[item_id]
                continue

            for patch in self[item_id]:
                # Another speedup
                if patch not in base[item_id]:
                    base[item_id][patch] = self[item_id][patch]
                    continue

                for item_version in self[item_id][patch]:
                    # if we hit here then item_id and patch are both in the base, and
                    # therefore we have a new version of the item at this patch level
                    base[item_id][patch].add(item_version)
