import collections
import logging

from backend.Proxy import Proxy
from backend.Worker import Worker
from backend.tools import *


class Scheduler:
    def __init__(self, crafts: list[list[str, str] | tuple[str, str]], proxies: list[Proxy], name: str = "Default",
                 log_level: str = logging.INFO):
        """
        Initialize a Scheduler.
        :param crafts: The crafts that have to be completed
        :param proxies: the proxies we can use to do the job
        :param name: The name of the Scheduler
        :param log_level: the log level of the internal logger
        """

        self.proxies = proxies

        # Prepare the deque
        self.crafts = collections.deque(maxlen=len(crafts))
        for item in crafts:
            self.crafts.append(item)

        self.workers = []
        self.craft_list = crafts
        self.max_workers = 5
        self.kill = False
        self.name = name
        self.logger = logging.getLogger(f"Scheduler({name})")
        self.logger.setLevel(log_level)
        self.progress = {"status": "not started"}  # Progress metrics for other scripts
        self.output_crafts = []

    def run(self):
        """
        Run the scheduler.
        :return: None
        """

        self.output_crafts = []
        self.workers = []

        # Prepare the Workers
        total_amount_of_crafts = len(self.craft_list)
        rank = rank_proxies(self.proxies)
        for id in range(self.max_workers):
            self.workers.append(Worker(self.proxies, self.crafts, rank[id], f"Tyler-{id}",
                                       return_craft_reference=self.output_crafts))

        start_time = time.time()
        # Start the Workers
        for w in self.workers:
            w.begin_working()
        base_completed = 0

        # Main loop
        while len(self.workers):
            # Calculate how many total jobs have been completed by the workers (for progress bar)
            completed = base_completed
            remove_these = []
            currently_alive = 0
            for w in self.workers:
                completed += w.completed
                if not w.is_working():  # Worker is done, mark for removal
                    remove_these.append(w)
                    continue
                currently_alive += 1

            for w in remove_these:
                base_completed += w.completed  # Update the base_completed
                # (so we don't have to lug around the whole object)
                self.workers.remove(w)  # Actually remove the worker
                del w  # BURN THEM

            # Calculate completed percentage and ETA
            complete_percentage = 100 * completed / total_amount_of_crafts

            if complete_percentage:
                current_time = time.time() - start_time
                total_time = (100 / complete_percentage) * current_time
                remaining_time = round(total_time - current_time, 2)

            else:
                remaining_time = "inf"

            # Log the information
            self.logger.info(f"Current overall progress: "
                             f"{completed}/{total_amount_of_crafts} ({round(complete_percentage, 2)}%,"
                             f" ETA: {remaining_time}s), Workers alive: {len(self.workers)}")
            self.progress = {"status": "running", "jobs_completed": self._generate_self_running(),
                             "completed": completed, "total_amount": total_amount_of_crafts,
                             "percentage_done": complete_percentage, "workers_alive": len(self.workers),
                             "eta": remaining_time}
            time.sleep(1)  # Reduced CPU usage by 78% on my computer

        self.progress["status"] = "finished"  # We're done!

    def _generate_self_running(self):
        """
        Generate a dictionary of the amount of work each worker has done. Meant for self.progress
        :return: the dictionary representing the amount of work done.
        """
        jobs_division = {}
        for w in self.workers:
            jobs_division[w.id] = w.completed

        return jobs_division
