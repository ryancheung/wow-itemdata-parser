from waybackpack import *

import argparse
import logging
import os
import urlparse

import threading
import time

logger = logging.getLogger()

class ModifiedPack(Pack):
    def __init__(self,
        url,
        timestamps=None,
        uniques_only=False,
        session=None):

        super(ModifiedPack, self).__init__(url, timestamps, uniques_only, session)

        print self.parsed_url

    def download_to(self, directory,
        raw=False,
        root=settings.DEFAULT_ROOT,
        ignore_errors=False):

        for asset in self.assets:
            path_head, path_tail = os.path.split(self.parsed_url.path)
            if path_tail == "":
                path_tail = "index.html"

            filedir = os.path.join(
                directory,
                asset.timestamp,
                self.parsed_url.netloc,
                path_head.lstrip("/")
            )
            prefix = ""
            if self.parsed_url.query != "":
                prefix = self.parsed_url.query + "-"
                
            filepath = os.path.join(filedir, prefix + path_tail)

            logger.info(
                "Fetching {0} @ {1}".format(
                    asset.original_url, 
                    asset.timestamp)
            )

            try:
                content = asset.fetch(
                    session=self.session,
                    raw=raw,
                    root=root
                )
            except Exception as e:
                if ignore_errors == True:
                    ex_name = ".".join([ e.__module__, e.__class__.__name__ ])
                    logger.error("ERROR -- {0} @ {1} -- {2}: {3}".format(
                        asset.original_url,
                        asset.timestamp,
                        ex_name,
                        e
                    ))
                    continue
                else:
                    raise

            try:
                os.makedirs(filedir)
            except OSError:
                pass
            with open(filepath, "wb") as f:
                logger.info("Writing to {0}\n".format(filepath))
                f.write(content)

class WaybackDump(object):
    def __init__(self, base_url, download_dir, from_date = "2004", to_date = "2006"):
        self.base_url = base_url
        self.download_dir = download_dir

        self.from_date = from_date
        self.to_date = to_date

        self._tasks = []
        self._threads = []

        self._finished_tasks = []

    def buildAndRetrievePack(self, suffix):
        try:
            url = self.base_url + suffix

            session = Session(
                user_agent=settings.DEFAULT_USER_AGENT,
                follow_redirects=True
            )

            snapshots = search(url,
                session=session,
                from_date=self.from_date,
                to_date=self.to_date,
                uniques_only=True,
                collapse=None
            )

            timestamps = [ snap["timestamp"] for snap in snapshots ]

            pack = ModifiedPack(
                url,
                timestamps=timestamps,
                session=session
            )

            pack.download_to(
                self.download_dir,
                raw=True,
                root=settings.DEFAULT_ROOT,
                ignore_errors=True
            )
        except Exception as e:
            print e
            print "Exception getting pack. Retry"

            self.buildAndRetrievePack(suffix)

    def task_completed(self, task):
        self._finished_tasks.append(task)

    def generate_tasks(self):
        raise NotImplementedError("WaybackDump must implement generate_tasks")

    def execute(self):
        self.generate_tasks()
        # Do the tasks in separate threads
        for task in self._tasks:
            t = threading.Thread(target = task.execute)

            self._threads.append(t)
            t.daemon = True
            t.start()

    @property
    def finished(self):
        return len(self._tasks) == len(self._finished_tasks)

class WaybackDumpTask(object):
    def __init__(self, master):
        self.master = master

    def acquire_packs(self):
        raise NotImplementedError("WaybackDumpTask must implement acquire_packs")

    def execute(self):
        self.acquire_packs()

        self.master.task_completed(self)

"""
        ALLAKHAZAM

"""
class AllakhazamItemTask(WaybackDumpTask):
    def __init__(self, master):
        super(AllakhazamItemTask, self).__init__(master)

    def acquire_packs(Self):
        # Get all individual item IDs
        for i in xrange(1, 24284):
            self.buildItemPack(i)

    def buildItemPack(self, itemId):
        return self.master.buildAndRetrievePack("item.html?witem=%d" % itemId)

class AllakhazamItemSetTask(WaybackDumpTask):
    def __init__(self, master):
        super(AllakhazamItemSetTask, self).__init__(master)

    def acquire_packs(self):
        # Get item set pages. There are 172 sets in the game ranging from low
        # 100 IDs to high 500 IDs, just check the range. Anything not existing
        # will be ignored anyway
        for i in xrange(1, 600):
            self.buildItemSetPack(i)

    def buildItemSetPack(self, setId):
        return self.master.buildAndRetrievePack("db/itemset.html?setid=%d" % setId)

class AllakhazamItemEntryTask(WaybackDumpTask):
    def __init__(self, master):
        super(AllakhazamItemEntryTask, self).__init__(master)

    def acquire_packs(self):
        # Get item entries, will be misses
        for i in xrange(2000, 60000):
            self.buildItemEntryPack(i)

    def buildItemEntryPack(self, entryId):
        return self.master.buildAndRetrievePack("db/item.html?entryid=%d" % entryId)

class AllakhazamItemPriceTask(WaybackDumpTask):
    def __init__(self, master):
        super(AllakhazamItemPriceTask, self).__init__(master)

    def acquire_packs(self):
        # Get all individual item IDs. Price may have multiple snapshots
        # that differ to the plain item info
        for i in xrange(1, 24284):
            self.buildItemPricePack(i)

    def buildItemPricePack(self, itemId):
        return self.master.buildAndRetrievePack("db/price.html?witem=%d" % itemId)

class AllakhazamWayback(WaybackDump):
    def __init__(self, download_dir):
        super(AllakhazamWayback, self).__init__("http://wow.allakhazam.com/", download_dir)

    def generate_tasks(self):
        pass
        #self._tasks.append(AllakhazamItemTask(self))
        #self._tasks.append(AllakhazamItemSetTask(self))
        #self._tasks.append(AllakhazamItemEntryTask(self))
        #self._tasks.append(AllakhazamItemPriceTask(self))

"""
        THOTT BOT

"""
class ThottbotRangedWeaponTask(WaybackDumpTask):
    def __init__(self, master):
        super(ThottbotRangedWeaponTask, self).__init__(master)

    def acquire_packs(self):
        self.master.buildAndRetrievePack("?r=ranged")

class ThottbotItemSetTask(WaybackDumpTask):
    def __init__(self, master):
        super(ThottbotItemSetTask, self).__init__(master)

    def acquire_packs(self):
        for i in xrange(1, 600):
            self.buildItemSetPack(i)

    def buildItemSetPack(self, setId):
        return self.master.buildAndRetrievePack("?set=%d" % setId)

class ThottbotProfessionTask(WaybackDumpTask):
    def __init__(self, master):
        super(ThottbotProfessionTask, self).__init__(master)

    def acquire_packs(self):
        for prof in ["Tailoring", "Blacksmithing", "Leatherworking", "Engineering"]:
            self.buildProfPack(prof)

    def buildProfPack(self, prof):
        return self.master.buildAndRetrievePack("?t=%s" % prof)

class ThottbotItemEntryTask(WaybackDumpTask):
    def __init__(self, master):
        super(ThottbotItemEntryTask, self).__init__(master)

    def acquire_packs(self):
        # Item entries, will be lots of misses, but check a big range
        for i in xrange(1, 60000):
            self.buildItemPack(i)

    def buildItemPack(self, itemId):
        return self.master.buildAndRetrievePack("?i=%d" % itemId)

class ThottbotWayback(WaybackDump):
    def __init__(self, download_dir):
        super(ThottbotWayback, self).__init__("http://thottbot.com/", download_dir)

    def generate_tasks(self):
        # Easy list of all ranged weapons
        #self._tasks.append(ThottbotRangedWeaponTask(self))

        # Sets
        #self._tasks.append(ThottbotItemSetTask(self))

        # Professions
        #self._tasks.append(ThottbotProfessionTask(self))

        # Items. Not sorted by item ID, just entries discovered by the database.
        #self._tasks.append(ThottbotItemEntryTask(self))
        pass

def main():
    logging.basicConfig(
        level=(logging.INFO),
        format="%(levelname)s:%(name)s: %(message)s"
    )

    allakhazam = AllakhazamWayback("waybackdump")
    #allakhazam.execute()

    thottbot = ThottbotWayback("waybackdump")

    dumps = [ allakhazam, thottbot ]
    
    try:
        for d in dumps:
            d.execute()

        time.sleep(5) # 5 secs for other threads to boot up
        # Keep the main thread busy until all tasks have completed?
        while 1:
            finished = True
            for d in dumps:
                if not d.finished:
                    finished = False

            if finished:
                break

            time.sleep(1)

    except KeyboardInterrupt:
        quit()

if __name__ == "__main__":
    main()
