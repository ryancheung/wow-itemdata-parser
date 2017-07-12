import csv
import json
import re

# Core bonding enum, for auto updating of bonding type?
BIND_TYPES = {
    "NO_BIND"                                     : 0,
    "BIND_WHEN_PICKED_UP"                         : 1,
    "BIND_WHEN_EQUIPPED"                          : 2,
    "BIND_WHEN_USE"                               : 3,
    "BIND_QUEST_ITEM"                             : 4,
}

NAME_TO_ID_HASH = {}
ID_TO_NAME_HASH = {}
DB_ITEM_DATA = {}
with open("item_db.csv", "rb") as f:
    # entry, itemlevel, name, flags, class, quality, randomproperty
    for row in csv.reader(f):
        NAME_TO_ID_HASH[row[2]] = int(row[0])
        ID_TO_NAME_HASH[int(row[0])] = row[2]

        DB_ITEM_DATA[int(row[0])] = {
            "name": row[2],
            "itemlevel": int(row[1]),
            "quest": int(row[4]) == 12,
            "trade_good": int(row[4]) == 7,
            "quality": int(row[5]),
            "random_property": int(row[6])
        }

def ItemNameToID(name):
    # go through item list, find name, return ID. Exact match for now
    if name is None:
        return -1

    if name in NAME_TO_ID_HASH:
        return NAME_TO_ID_HASH[name]

    return -1

def ItemHasRandomAffix(item_name):
    name = ItemRandomSuffixStrip(item_name)
    
    return name != item_name

suffix_regex = re.compile(r"(.*)\sof\s?(the)?\s?(\w+)\s?(Resistance|Wrath)?")

def ItemRandomSuffixStrip(name):
    # of Stamina
    # of Intellect
    # of Healing
    # of the Bear
    # of the Whale
    # of Frozen Wrath
    # of Beastslaying
    # of Fire Resistance
    of_the_suffix = ["Tiger", "Bear", "Gorilla", "Boar", "Monkey", "Falcon",
        "Wolf", "Eagle", "Whale", "Owl"]

    resistance_suffix = [ "Nature", "Frost", "Fire", "Arcane", "Shadow" ]

    wrath_suffix = [ "Frozen", "Arcane", "Fiery", "Nature's", "Shadow" ]

    flat_suffix = [ "Stamina", "Intellect", "Spirit", "Strength", "Agility", "Healing",
        "Striking", "Sorcery", "Regeneration", "Concentration", "Regeneration", "Power" ]


    res = suffix_regex.search(name)

    # Not a random suffix
    if not res:
        return name

    item_name = res.group(1)

    if res.group(2) is not None:
        # of_the_suffix
        if res.group(3) not in of_the_suffix:
            return name
    elif res.group(4) is not None:
        if res.group(4) == "Wrath":
            if res.group(3) not in wrath_suffix:
                return name
        elif res.group(4) == "Resistance":
            if res.group(3) not in resistance_suffix:
                return name
    elif res.group(3) not in flat_suffix: # of X suffix
        return name

    # Is random suffix item, return stripped name!
    return item_name

class ItemVersion(dict):
    def __init__(self, *args, **kwargs):
        super(ItemVersion, self).__init__(*args, **kwargs)

        if "conflicts" not in self:
            self["conflicts"] = []

    def __hash__(self):
        return id(json.dumps(self.hash_safe(), sort_keys = True))

    def hash_safe(self):
        # Strip unnecessary keys from the dict for hashing so we can avoid
        # duplicates
        copy = self.copy()
        del copy["flavour"]
        del copy["conflicts"]

        return copy

    def calculate_diff(self, other):
        if not isinstance(other, ItemVersion):
            raise RuntimeError("Cannot compare item diff between non-item")

        diff = ItemVersionDifference()

        for key in self:
            if key == "conflicts" or key == "patch":
                continue

            # Resists
            if isinstance(self[key], dict):
                for subkey in self[key]:
                    diff.add_resist_diff(subkey, self, other)
            elif key == "effects":
                diff.add_effects_diff(key, self, other)
            else:
                diff.add_diff(key, self, other)

        return diff

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

class ItemVersionDifference(ItemVersion):
    def __init__(self, *args, **kwargs):
        super(ItemVersionDifference, self).__init__(*args, **kwargs)

        # Initialize
        tmp = ItemVersion.new()
        for key in tmp:
            self[key] = tmp[key]

    def add_diff(self, key, me, other):
        # Ignore values which are the same
        if key in me and key not in other:
            return

        if key not in me and key in other:
            self[key] = other[key]

        elif me[key] == other[key] and key in self:
            del self[key]
        
        else:
            self[key] = other[key]

    def add_resist_diff(self, subkey, me, other):
        if me["resistances"][subkey] == other["resistances"][subkey]:
            del self["resistances"][subkey]
            return

        self["resistances"][subkey] = other["resistances"][subkey]

    def add_effects_diff(self, key, me, other):
        for spell_index in range(1,6):
            if spell_index >= len(me[key]):
                my_effect = None
            else:
                my_effect = me[key][spell_index]

            if spell_index >= len(other[key]):
                other_effect = None
            else:
                other_effect = other[key][spell_index]

            if my_effect != other_effect and other_effect is not None:
                self[key].append(ItemSpell(spell_index, other_effect["spellId"], other_effect["tooltip"]))


class ItemSpell(dict):
    def __init__(self, idx, spellId, tooltip, *args, **kwargs):
        super(ItemSpell, self).__init__(*args, **kwargs)

        self["index"] = idx
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
