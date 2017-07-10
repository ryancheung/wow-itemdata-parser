"""
parser.py

Parse all downloaded wayback item records and store them in an easy to read
JSON object
"""

import os
import re
import json
import traceback

from archiveparser import *
from items import *

from bs4 import BeautifulSoup

from pprint import pprint

# Inside each snapshot is a folder named "wow.allakhazam.com", "thottbot.com" or other 
# archive to parse
WOW_DB_DIRS = {
    "wow.allakhazam.com": {
        "parser": AllakhazamFileParser
    },
    "thottbot.com": {
        "parser": ThottbotFileParser
    },
    "www.thottbot.com": {
        "parser": ThottbotFileParser
    }
}
    
# 2004 format is just butchered HTML, not clean to parse with the rest
def getItemData2004(item_div):
    pass

def getPatchLevel(snapshot):
    # Basic arbitration on patch level using the snapshot date.
    # Snapshot format is YYYYMMDDhhmmss
    s = int(snapshot)

    if (s < 20050307000000):
        return 102 # patch 1.2
    elif (s >= 20050307000000 and s < 20050505000000):
        return 103 # patch 1.3
    elif (s >= 20050505000000 and s < 20050712000000):
        return 105 # patch 1.4-1.5
    elif (s >= 20050712000000 and s < 20050913000000):
        return 106 # patch 1.6
    elif (s >= 20050913000000 and s < 20051010000000):
        return 107 # patch 1.7
    elif (s >= 20051010000000 and s < 20060103000000):
        return 108 # patch 1.8
    elif (s >= 20060103000000 and s < 20060328000000):
        return 109 # 1.9
    elif (s >= 20060328000000 and s < 20060620000000):
        return 110 # 1.10
    elif (s >= 20060620000000 and s < 20060822000000):
        return 111 # 1.11
    else:
        return 112 # 1.12

def parse_directory(directory, patchLevel, parser):
    # Dict of all items parsed in this directory, similar to the top-level items. merge after each parse
    # Walk over each item in the snapshot - can be multiple items in a single snap

    tmp = ItemStore()
    for item_snapshot in os.listdir(directory):
        file_path = os.path.join(directory, item_snapshot)
        print file_path
        if os.path.isdir(file_path):
            # Subdirectory, parse recursively and merge
            parse_directory(file_path, patchLevel, parser).merge_into(tmp)
            continue

        with open(file_path, "rb") as fitem:
            # Parse the HTML file
            soup = BeautifulSoup(fitem.read(), "html.parser")

            parser_instance = parser(soup)
            try:
                parser_instance.parse()
            except:
                print "Exception processing item - dir: %s, snapshot: %s" % (directory, item_snapshot)
                raise

            for item in parser_instance.items:
                try:
                    if "witem=" in item_snapshot:
                        item_id = int(item_snapshot.split("=")[1].split("-")[0])
                    else:
                        item_id = ItemNameToID(item["name"])

                        # of the Boar, of the Eagle, etc
                        if item_id < 0 and item["name"] is not None and ("of the" in item["name"]):
                            try:
                                item_id = ItemNameToID(item["name"][:item["name"].index("of")-1])
                            except ValueError:
                                pass

                    if item_id < 0:
                        print "Item %s has no ID (%s @ %s)" % (item["name"], item_snapshot, directory)
                        continue

                    # fix item quality, 0-5
                    item["quality"] = parser_instance.get_quality(item["quality"])

                    # Some unequippable item that we don't care about, likely from crafting
                    # or disenchant info?
                    #if not item["slot"]:
                    #    continue

                    tmp.add_item(item_id, patchLevel, item)
                except Exception as e:
                    print "Exception handling processed item"
                    pprint(item)
                    traceback.print_exc()

    return tmp

# Enable json serialization of the item sets
class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if (isinstance(obj, set)):
            return list(obj)

        return json.JSONEncoder.default(self, obj)


def main():
    # Storage format is: items: { itemId: { patchLevel: [{itemVersion}, ...], ... } }
    items = ItemStore()

    DB_DUMP_DIR = os.path.join(os.getcwd(), "waybackdump")

    for snapshot in os.listdir(DB_DUMP_DIR):
        snapshot_dir = os.path.join(DB_DUMP_DIR, snapshot)
        # Skip non-snapshot directories in current working dir
        if not os.path.isdir(snapshot_dir):
            continue

        # Ignore snapshots from before 2004 or after 2006
        s_year = int(snapshot[0:4])
        if s_year < 2004 or s_year >= 2007:
            continue

        patchLevel = getPatchLevel(snapshot)

        for db in WOW_DB_DIRS:
            item_dir = os.path.join(snapshot_dir, db)
            if os.path.exists(item_dir) and os.path.isdir(item_dir):
                parser = WOW_DB_DIRS[db]["parser"]

                parse_directory(item_dir, patchLevel, parser).merge_into(items)
        
        #if len(items.keys()) > 20:
        #    break

    #pprint(items)

    with open("parsed.json", "wb") as f:
        json.dump(items, f, cls = CustomEncoder)

main()
