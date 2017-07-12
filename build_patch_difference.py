import json
import operator
import re

from collections import OrderedDict

from pprint import pprint

from items import *

class ItemPatchData(object):
    def __init__(self, patch_level):
        self.patch_level = patch_level

        self.item_store = ItemStore()
        self.not_found = []

        self.filtered_item_store = ItemStore()
        self.filtered_not_found = []

        self.filtered = False

    def build_patch_data(self, data):
        # Find the latest version of an item before or at the specified patch level
        # That's the best we can do if there are no records for our desired patch

        for name, item_id in NAME_TO_ID_HASH.iteritems():
            # Skip database monster items
            if "Monster -" in name:
                continue

            if item_id not in data:
                self.not_found.append(item_id)
                continue

            patches = data[item_id].keys()
            patches.sort() # sorted lowest patch to highest

            done = False
            prev_patch = 0
            for patch in patches:
                # beyond our desired patch, item does not exist in the
                # patch we want or not found
                if patch > self.patch_level:
                    done = True
                    break

                # Remove previous patch data since we have data for a more
                # recent patch
                if prev_patch > 0:
                    del self.item_store[item_id][prev_patch]

                for itemv in data[item_id][patch]:
                    self.item_store.add_item(item_id, patch, itemv)

                prev_patch = patch

            # Item not found in this patch, nor an earlier version from a previous
            # patch. Must have been added later or no record
            if prev_patch == 0 and not done:
                self.not_found.append(item_id)

    def filter(self):
        # Filter out trade goods and quest items from item store
        marked_for_deletion = []
        tmp = ItemStore(self.item_store)

        for item_id in tmp:
            for patch_level in tmp[item_id]:
                for itemv in tmp[item_id][patch_level]:
                    if itemv["quest"] or itemv["trade_good"] or itemv["quality"] == 0:
                        marked_for_deletion.append(item_id)
                        break

        for item_id in marked_for_deletion:
            del tmp[item_id]

        tmp.merge_into(self.filtered_item_store)

        # Same with not found, ignore grey items too
        for item_id in self.not_found:
            item = DB_ITEM_DATA[item_id]
            if (not item["quest"] and not item["trade_good"] and item["quality"] > 0):
                self.filtered_not_found.append(item_id)

        self.filtered = True

    def calculate_diff(self, from_data):
        """
        Build the diff between two patches. We want to go TO the CURRENT patch data
        in this object, from the FROM_DATA. It can be a downgrade or an upgrade. Set
        item stats and update the removed/added items based on current patch. Both
        data need to have been filtered first
        """
        if not isinstance(from_data, ItemPatchData):
            raise RuntimeError("Cannot compare the diff between non-patch data objects")

        if not self.filtered or not from_data.filtered:
            raise RuntimeError("Item patch data must be filtered before performing diff, or the wrong items may be removed")

        item_diff = {}

        # The item store only has items at a single patch level. It may not be
        # the current patch level if it was only seen at an earlier patch
        for item_id in self.filtered_item_store:
            item_diff[item_id] = { 
                "from": None,
                "to": None,
                "removed": False
            }

            current_plevel = self.filtered_item_store[item_id].keys()[0]
            current_versions = self.filtered_item_store[item_id][current_plevel]

            concensus = self.build_item_concensus(current_versions)
            concensus["patch"] = current_plevel

            item_diff[item_id]["to"] = concensus

            if item_id in from_data.filtered_item_store:
                # item possibly updated
                from_plevel = from_data.filtered_item_store[item_id].keys()[0]
                from_versions = from_data.filtered_item_store[item_id][from_plevel]

                from_concensus = self.build_item_concensus(from_versions)
                from_concensus["patch"] = from_plevel

                item_diff[item_id]["from"] = from_concensus

        removed_items = self.filtered_not_found
        for item_id in from_data.filtered_item_store:
            if item_id not in item_diff:
                removed_items.append(item_id)

        for item_id in set(removed_items):
            item_diff[item_id] = {
                "removed": True
            }

        return OrderedDict(sorted(item_diff.iteritems(), key = lambda i: i[0]))

    def build_item_concensus(self, item_versions):
        """
        Have a list of item versions, iterate over them to find the most common version
        and return that. Make a list of conflicts inside the item too for the differing versions
        """

        #print "FINDING ITEM CONCENSUS"
        #pprint(item_versions)

        most_common = None
        conflicts = []

        occurrences = {}
        mapping = {}

        for version in item_versions:
            item_hash = hash(version)

            if item_hash not in mapping:
                mapping[item_hash] = version
            if item_hash not in occurrences:
                occurrences[item_hash] = 0

            occurrences[item_hash] += 1

        #pprint(occurrences)
        #pprint(mapping)

        concensus_hash = max(occurrences.iteritems(), key = operator.itemgetter(1))[0]
        concensus = mapping[concensus_hash]

        #print "Concensus is %s" % (concensus_hash,)

        for mhash in mapping:
            if mhash != concensus_hash:
                conflict_version = mapping[mhash]
                
                conflicts.append(concensus.calculate_diff(conflict_version))


        concensus["conflicts"] += conflicts

        #pprint(concensus)

        return concensus

def build_sql_migration(outfile, diff):
    for item_id in diff:
        identifier_tuple = (ID_TO_NAME_HASH[item_id], DB_ITEM_DATA[item_id]["itemlevel"], item_id)

        if item_id == 19165:
            pprint(diff[item_id])

        item_data = diff[item_id]

        if item_data["removed"]:
            outfile.write("-- ITEM NOT FOUND: %s (ilevel %d, entry %d)\n" % identifier_tuple)
            outfile.write("REPLACE INTO `forbidden_items` (SELECT `entry` FROM `item_template` WHERE `entry` = %d;\n" % (item_id,))
            continue

        
        # New item available in this patch
        if item_data["from"] is None:
            outfile.write("-- NEW ITEM ADDED: %s (ilevel %d, entry %d)\n" % identifier_tuple)
            continue

        # Item present in both to and from patch level. Possibly updated
        if hash(item_data["to"]) == hash(item_data["from"]):
            outfile.write("-- NO CHANGE: %s (ilevel %d, entry %d)\n" % identifier_tuple)
            continue

        # Item changed between patches!
        item_diff = item_data["from"].calculate_diff(item_data["to"])

        outfile.write("-- ITEM %s (ilevel %d, entry %d) CHANGED\n" % identifier_tuple)

        def write_conflict(param, value):
            value = re.sub(r'[^\x00-\x7F]+', '', value)
            outfile.write("-- DESTINATION SOURCE CONFLICT `%s` = `%s`\n" % (param, value))

        def write_change(param, value):
            value = re.sub(r'[^\x00-\x7F]+', '', value)
            outfile.write("-- Modified %s to %s\n" % (param, value))

        for conflict in item_data["to"]["conflicts"]:
            for key in conflict:
                if key == "flavour" or key == "name" or key == "conflicts" or key == "itemType" or key == "slot": 
                    continue

                if key == "effects":
                    for effect in conflict[key]:
                        conflict_param = "Spell index %d (%s)" % (effect["index"], effect["spellId"])
                        conflict_value = effect["tooltip"]

                        write_conflict(conflict_param, conflict_value)

                elif key == "resistances":
                    for res in conflict[key]:
                        conflict_param = "%s_res" % (res,)
                        conflict_value = conflict[key][res]

                        write_conflict(conflict_param, conflict_value)
                else:
                    write_conflict(key, conflict[key])

        query = "UPDATE `item_template` SET "
        first = True

        for key in item_diff:
            if key == "flavour" or key == "name" or key == "conflicts" or key == "itemType" or key == "slot":
                continue

            if not first:
                query += ", "

            if key == "effects":
                first_effect = True
                for effect in item_diff[key]:
                    spell_id = effect["spellId"]
                    index = effect["index"]
                    tooltip = effect["tooltip"]
                    if spell_id < 0:
                        # TODO: Look up spell ID based on tooltip
                        continue
                    
                    if not first_effect:
                        query += ", "

                    param = "Spell #%d" % (index,)
                    value = "%d (%s)" % (spell_id, tooltip)
                    write_change(param, value)

                    trigger = 1
                    if "Use:" in tooltip:
                        trigger = 2

                    query += "`spellid_%d` = %d, `spelltrigger_%d` = %d" % (index, spell_id, index, trigger)

                    first_effect = False

            elif key == "resistances":
                first_resist = True

                for res in item_diff[key]:
                    res_key = "%s_res" % (res,)
                    write_change(res_key, item_diff[key][res])

                    if not first_resist:
                        query += ", "

                    query += "`%s` = `%d`" % (res_key, item_diff[key][res])
                    first_resist = False
            else:
                write_change(key, item_diff[key])

                query += "`%s` = `%d`" % (key, item_diff[key])

            first = False

        outfile.write(query + ";\n")

def main():
    to_patch = 106
    from_patch = 107

    with open("parsed.json", "rb") as f:
        item_data = ItemStore()

        tmp = json.load(f)

        # Convert unicode keys back to int, json has no int keys
        for item_id in tmp:
            for patch_level in tmp[item_id]:
                for itemv in tmp[item_id][patch_level]:
                    item_data.add_item(int(item_id), int(patch_level), ItemVersion(itemv))

    to_data = ItemPatchData(to_patch)
    to_data.build_patch_data(item_data)
    to_data.filter()
    #pprint(to_data.item_store)
    #pprint(to_data.filtered_not_found)

    from_data = ItemPatchData(from_patch)
    from_data.build_patch_data(item_data)
    from_data.filter()

    print "Num items in 106: %d, not found: %d" % (len(to_data.item_store.keys()), len(to_data.not_found))
    print "Num items in FILTERED 106: %d, not found: %d" % (len(to_data.filtered_item_store.keys()), len(to_data.filtered_not_found))
    
    print "Num items in 107: %d, not found: %d" % (len(from_data.item_store.keys()), len(from_data.not_found))
    print "Num items in FILTERED 107: %d, not found: %d" % (len(from_data.filtered_item_store.keys()), len(from_data.filtered_not_found))

    diff = to_data.calculate_diff(from_data)

    # Build SQL file with statements to update stats/remove items
    outfile = "item_update_%d_to_%d.sql" % (from_patch, to_patch)
    with open(outfile, "wb") as f:
        build_sql_migration(f, diff)

    #with open("patchdiff.json", "wb") as f:
    #    json.dump(diff, f)

main()
