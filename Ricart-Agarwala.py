from time import sleep
from multiprocessing import Pool, Process, Manager
import random
from itertools import repeat

# time spent in critical section, in seconds
SLEEP_TIME = 0.5
# interval to print the status of the nodes
UPDATE_TIME = 0.3

class Node:

    def __init__(self, manager, id_, n):
        # 0 -> not requesting, 1 -> requesting, 2 -> in cs, 3 -> done
        self.status = manager.Value('i', 0)
        self.status_lock = manager.Lock() # mutex for the status variable
        self.semaphore = manager.Semaphore(0) # sem to wait on for all go-ahead messages
        self.ts = manager.Value('i', 0) # local timestamp
        self.clock = manager.Value('i', 0) # local clock
        self.request_queue = manager.list() # queue of requests made while in cs
        self.id_ = manager.Value('i', id_) # node id
        self.neighbors = n # array of neighbors
        self.approved = manager.Value('i', 0)

    def tick(self, max_ts):  # main event loop
        while self.ts.value < max_ts:
            # sleep for random interval of time
            sleep(random.random())
            sleep(random.random())
            sleep(random.random())
            # randomly decide whether to request
            maycall = random.randint(0, 2)
            if maycall:
                self.request()
        with self.status_lock:
            self.status.set(3)

    def print(self, *args, force=False):
        pass
        if force:
            print(self, ":", *args)

    def request(self):
        #self.print("starting request")
        with self.status_lock:
            self.status.set(1)  # set the status
            self.ts.set(self.clock.value)  # get a timestamp
            self.clock.set(self.clock.value + 1) # increment the clock
        for neighbor in self.neighbors:  # ask for all tokens at once
            if neighbor == self:  # skip self
                continue
            #self.print("asking :", neighbor)
            neighbor.grant(self)
        #self.print("starting wait")
        for i in range(len(self.neighbors) - 1):  # wait until everyone grants
            self.semaphore.acquire()
            self.approved.set(i + 1)
            #self.print()

        # now execute the cs
        self.critical_section()

    def critical_section(self):
        with self.status_lock:
            self.status.set(2)  # set the status
        # critical section
        #self.print("enter cs")
        sleep(SLEEP_TIME)
        #self.print("exit cs")
        with self.status_lock:
            # grant all the requests in the queue
            while len(self.request_queue) > 0:
                sem, node = self.request_queue.pop()
                #print("notifying :", self.neighbors[node.value])
                sem.release()
            # reset the status
            self.status.set(0)
            self.clock.set(self.clock.value + 1) # increment clock
        self.approved.set(0)

    def grant(self, neighbor):
        #self.print("asked by :", neighbor)
        with self.status_lock:  # make sure only one thread calls this
            #self.print("asked by (inside lock) :", neighbor, self.status, self.ts.value, neighbor.ts.value)
            if self.status.value == 0 or self.status.value == 3:  # if we are free or done, we grant
                #self.print("free : allowing :", neighbor)
                neighbor.semaphore.release()
            elif self.status.value == 1 and (self.ts.value > neighbor.ts.value):
                #self.print("on request : allowing :", neighbor)
                neighbor.semaphore.release()
            elif self.status.value == 1 and (self.ts.value == neighbor.ts.value and self.id_.value > neighbor.id_.value):
                #self.print("on request : ts tie : allowing :", neighbor)
                neighbor.semaphore.release()
            else:  # either we're in cs or requesting with a lower ts
                # we put the sem in a queue to be unlocked when
                # we exit from the cs
                #if self.status.value == 2:
                #    self.print("in cs : holding :", neighbor)
                #else:
                #    self.print("on request : holding :", neighbor)
                self.request_queue.append((neighbor.semaphore, neighbor.id_))

            # we follow lamport's clock model, and update local clock
            # whenever we receive a message from a node with a greater
            # local clock
            if self.clock.value <= neighbor.clock.value:
                self.clock.set(neighbor.clock.value + 1)
        #self.print("asked by (done) :", neighbor)

    def get_status(self):
        return (self.status.value, self.ts.value, self.approved.value)

    def __repr__(self):
        return "[Node %d, approved by %d nodes]" % (self.id_.value, self.approved.value)

# queries and prints the status of all the neighbors
def print_status(neighbors):
    STATUS_TEXT = ["free", "Requesting", "IN CRITICAL SECTION", "done"]
    while True:
        i = 0
        for neighbor in neighbors:
            stat = neighbor.get_status()
            print("Node %2d: %20s (local timestamp: %2d) (approved by: %2d nodes)" %
                  (i, STATUS_TEXT[stat[0]], stat[1], stat[2]))
            i += 1
        print()
        sleep(UPDATE_TIME)

# initiates the free -> request -> cs tick loop for
# each of the node
def start_tick(neighbors, node, max_ts):
    neighbors[node].tick(max_ts)

def main():
    import sys
    try:
        num_nodes = int(input("enter number of nodes"))
    except:
        print("[Error] Invalid number of nodes passed as argument!")
        return

    # mp manager to acquire shared locks
    manager = Manager()

    # initialization of all the neighbors
    neighbors = []
    for i in range(num_nodes):
        neighbors.append(Node(manager, i, neighbors))

    # the nodes stop after this many total requests are made
    max_ts = num_nodes * 3

    # printer process initiation
    # the printer process is independent from the worker
    # pool which manages the nodes. it wakes up at UPDATE_TIME
    # interval, queries and prints the statuses of all the
    # nodes, and sleeps again
    printer = Process(target=print_status, args=(neighbors,), daemon=True)
    printer.start()

    # the worker pool
    # it contains one process for each of the node in the
    # network. each process gets assigned to perform the
    # free -> request -> cs loop for one node.
    jobPool = Pool(processes=len(neighbors))
    jobPool.starmap(start_tick, zip(repeat(neighbors), range(len(neighbors)), repeat(max_ts)))


if __name__ == "__main__":
    main()
