import re

from pprint import pprint

from bs4 import BeautifulSoup

from items import *

# Regex for data parsing. Shared across most implementations, since they imitate
# in-game tooltips of the same format
armor_regex = re.compile(r"(\d+) Armor")
damage_spread_reg = re.compile(r"(\d+)\s+-\s+(\d+)\s+Damage")
speed_reg = re.compile(r"Speed\s+(\d+)")
stat_regex = re.compile(r"((\+|\-)[0-9]+) (Spirit|Strength|Agility|Stamina|Intellect)")
resist_regex = re.compile(r"((\+|\-)[0-9]+) (Arcane|Fire|Frost|Shadow|Nature|Holy) Resistance")
level_regex = re.compile(r"Requires Level (\d+)")
equipslot_regex = re.compile(r"(Head|Neck|Shoulder|Chest|Shirt|Bracer|One-Hand|Two-Hand|Main Hand|Off Hand|Hands|Waist|Legs|Boots|Trinket|Ring)")
quest_regex = re.compile(r"Quest Item")
trade_goods_regex = re.compile(r"Trade Goods")

class ArchiveFileParser(object):
    """
    Parses an individual HTML file, does not handle directories
    """
    def __init__(self, soup):
        self.items = set() # all items in this file

        """
        soup is the BeautifulSoup-ified data from a raw archive HTML file
        """
        self.soup = soup

        self._ignored_name_phrases = [] #["Elixir", "Potion", "Pattern", "Formula", "Recipe"]
        self._ignored_info_phrases = ["Unknown Item"] #"Slot Bag", "Ammo", "Projectile", "Quest Item", "Trade Goods"

    def parse(self):
        raise NotImplementedError("ArchiveDataParser must implement parse")

    def get_quality(self, quality_class):
        """
        Translate a quality class qualifier to real item quality value
        """
        raise NotImplementedError("ArchiveDataParser must implement get_quality")

    def parse_tooltip_field(self, itemVersion, field):
        # Don't parse any additional fields on trade goods or quest items
        if itemVersion["quest"] or itemVersion["trade_good"]:
            return

        if field.td is None:
            print "None TD found in field %s, item: %s" % (field, itemVersion["name"])
            return

        # Equippable status or item type/equip slot if no bonding
        if "Binds on" in field.text or "Binds when" in field.text or "Soulbound" in field.text:
            bonding = BIND_TYPES["BIND_WHEN_EQUIPPED"] if "equipped" in field.text else BIND_TYPES["BIND_WHEN_PICKED_UP"]
            itemVersion["bonding"] = bonding

        elif equipslot_regex.search(field.td.text) is not None:
            # Item type, equip slot
            tds = field.findChildren()
            itemVersion["slot"] = tds[0].text

            # Profession tool, no slot definition?
            if len(tds) > 1:
                itemVersion["itemType"] = tds[1].text

        elif "Armor" in field.text:
            # Armour/damage spread
            res = armor_regex.search(field.td.text)
            if res:
                itemVersion["armor"] = int(res.group(1))

        elif damage_spread_reg.search(field.td.text) is not None:
            # two cols, 119 -  180 Damage and Speed 3.70
            # TODO: Items with multiple damage types on them
            tds = field.findChildren()

            dmg = damage_spread_reg.search(tds[0].text)
            if dmg is not None:
                itemVersion["mindamage"] = int(dmg.group(1))
                itemVersion["maxdamage"] = int(dmg.group(2))

            # Projectiles (Ammo) only have damage, no speed
            if len(tds) > 1:
                speed = speed_reg.search(tds[1].text)
                if speed is not None:
                    itemVersion["speed"] = int(speed.group(1))
        elif quest_regex.search(field.td.text) is not None:
            itemVersion["quest"] = True

        elif trade_goods_regex.search(field.td.text) is not None:
            itemVersion["trade_good"] = True

        else:
            # The following rows can be any stat values, including str/int/stam/spi/agi and resists
            # up to the required level
            stat = stat_regex.search(field.td.text)
            resist = resist_regex.search(field.td.text)
            level = level_regex.search(field.td.text)
            if stat is not None:
                # Ignore stats on items with random affixes
                if ItemHasRandomAffix(itemVersion["name"]):
                    return

                itemVersion[str(stat.group(3)).lower()] = int(stat.group(1))
            elif resist is not None:
                itemVersion["resistances"][str(resist.group(3)).lower()] = int(resist.group(1))
            elif level is not None:
                itemVersion["requiredlevel"] = int(level.group(1))
            else:
                # effects from spells
                spell_effects = field.td.findChildren("a", class_ = ["itemeffectlink", "spell"])
                spell_index = 0
                for effect in spell_effects:
                    for br in effect.find_all("br"):
                        br.replace_with(" ")

                    # Items with broken spell effects
                    try:
                        spellId = int(effect["href"].split("=")[1])
                    except:
                        spellId = -1

                    tooltip = effect.text

                    itemVersion["effects"].append(ItemSpell(spell_index, spellId, tooltip))
                    spell_index += 1

                # flavour text or profession requirement, whatever
                if len(spell_effects) == 0:
                    if "Equip:" in field.td.text:
                        # equip effect with unknown spell ID. add it. happens with early snapshots from thott
                        itemVersion["effects"].append(ItemSpell(len(itemVersion["effects"])+1, -1, field.td.text))
                    else:
                        itemVersion["flavour"] = field.td.text

class AllakhazamFileParser(ArchiveFileParser):
    def __init__(self, soup):
        super(AllakhazamFileParser, self).__init__(soup)

        self._quality = {
            "greyname": 0,
            "whitename": 1,
            "greenname": 2,
            "bluename": 3,
            "purplename": 4,
            "orangename": 5
        }

        self._font_quality = {
            "#9D9D9D": 0,
            "#FFFFFF": 1,
            "#1EFF00": 2,
            "#0070DD": 3,
            "#A434EE": 4,
            "#D17C22": 5
        }


    def parse(self):
        # item div always has class wowitem. sets have multiple item divs
        item_displays = self.soup.find_all("div", attrs = {"class": "wowitem"})
        for item_div in item_displays:
            #pprint(item_div)

            itemv = self.get_item_data(item_div)

            if itemv is not None:
                self.items.add(itemv)

    def get_quality(self, quality_class):
        if quality_class in self._quality:
            return self._quality[quality_class]
        elif quality_class in self._font_quality:
            return self._font_quality[quality_class]
        return 0

    def get_item_data(self, item_div):
        # Div containing item data. Items can either be inside the div as-is
        # or inside a nested table. There's a few different formats for the
        # data over the years
        # Don't parse elixirs/potions/pets/other random shit, only equippable items
        for phrase in self._ignored_info_phrases:
            if phrase in item_div.text:
                return None

        name_span_classes = self._quality.keys()
        itemVersion = ItemVersion.new()
        for sclass in name_span_classes:
            name = item_div.find("span", attrs = {"class": sclass})
            if name is not None:
                itemVersion["name"] = ItemRandomSuffixStrip(name.text)
                itemVersion["quality"] = sclass
                break

        if itemVersion["name"] is None:
            for fcolour in self._font_quality:
                name = item_div.find("font", attrs = {"color": fcolour})
                if name is not None:
                    itemVersion["name"] = ItemRandomSuffixStrip(name.text)
                    itemVersion["quality"] = fcolour
                    break

        if itemVersion["name"] is None:
            print "No name found for item"
            print item_div
            return None

        for phrase in self._ignored_name_phrases:
            if phrase in itemVersion["name"]:
                return None

        # Snapshots 2005-2006 have a table, after that the table is gone. Some items
        # don't have snapshots within this range but are still meant to be in the
        # game (never reported by users or not scraped? dunno)
        if item_div.table is not None:
            for child in item_div.table.findChildren(recursive = False):
                self.parse_tooltip_field(itemVersion, child)

        else:
            # different parsing if no table
            print "AllakhazamFileParser: Snapshot has no item div"

        #pprint(itemVersion)

        return itemVersion
        #pprint(item_div.table) 

class ThottbotFileParser(ArchiveFileParser):
    def __init__(self, soup):
        super(ThottbotFileParser, self).__init__(soup)

        self.script_tooltip_pattern = re.compile(r'"<table class=ttb', re.MULTILINE | re.DOTALL)

        self._quality = {
            "quality0":     0, 
            "quality-0":    0, 
            "quality1":     1, 
            "quality-1":    1, 
            "quality2":     2, 
            "quality-2":    2, 
            "quality3":     3, 
            "quality-3":    3, 
            "quality4":     4, 
            "quality-4":    4,
            "quality5":     5, 
            "quality-5":    5
        }

    def parse(self):
        # Simplest parse for thott, table w/ ttb class
        item_displays = self.soup.find_all("table", attrs = {"class": "ttb"})

        # another display for thott, script w/ tooltip info. need to do some processing
        # on the script tag to get nice data

        scripts = self.soup.find_all("script", text = self.script_tooltip_pattern)
        for script in scripts:
            # Process script tag and put it back into usable soup
            table_string = "=".join(script.text.split("=")[1:]).strip()[:-1].strip('"')
            #print table_string
            table = BeautifulSoup(table_string, "html.parser").table
            #pprint(table.text)
            item_displays.append(table)

        for display in item_displays:
            #print "Parsing display"
            #pprint(display)
            itemv = self.get_item_data(display)

            if itemv is not None:
                self.items.add(itemv)

    def get_quality(self, quality_class):
        if quality_class in self._quality:
            return self._quality[quality_class]
        return 0

    def get_item_data(self, display):
        # Don't parse elixirs/potions/pets/other random shit, only equippable items
        for phrase in self._ignored_info_phrases:
            if phrase in display.text:
                return None

        name_span_classes = self._quality.keys()
        itemVersion = ItemVersion.new()

        for sclass in name_span_classes:
            name = display.find("span", attrs = {"class": sclass})
            if name is not None:
                itemVersion["name"] = ItemRandomSuffixStrip(name.text)
                itemVersion["quality"] = sclass
                break

        if itemVersion["name"] is None:
            print "No name found for item"
            print display
            return None

        for phrase in self._ignored_name_phrases:
            if phrase in itemVersion["name"]:
                return None

        for child in display.children:
            self.parse_tooltip_field(itemVersion, child)


        return itemVersion
