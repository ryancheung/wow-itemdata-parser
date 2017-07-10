import json

from pprint import pprint

from items import *

class ItemPatchData(object):
    def __init__(self, patch_level):
        self.patch_level = patch_level

        self.item_store = ItemStore()

        self.not_found = []

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
    #pprint(to_data.item_store)
    pprint(to_data.not_found)

    #from_data = ItemPatchData(from_patch)
    #from_data.build_patch_data(item_data)

    print "Num items in 106: %d, not found: %d" % (len(to_data.item_store.keys()), len(to_data.not_found))
    #print "Num items in 107: %d" % (len(from_data.item_data.keys()),)

main()
