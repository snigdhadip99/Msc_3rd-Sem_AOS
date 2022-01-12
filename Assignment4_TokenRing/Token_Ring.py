from multiprocessing import Pool, Process, Manager
from time import sleep
import random
from itertools import repeat
import sys

SLEEP_TIME = 0.5
# interval to print the status of the nodes
UPDATE_TIME = 0.3


class Node:

    def __init__(self, id_, manager, q, qlock, watch, num_nodes):
        self.id_ = manager.Value('i', id_)
        self.queue = q  # queue
        self.queue_lock = qlock  # queue lock
        self.watch = watch  # semaphore
        self.num_nodes = num_nodes  # number of nodes in the network
        self.token = manager.Value('i', 0)
        self.token_lock = manager.Lock()
        self.my_requests = manager.Value('i', 0)
        self.request_done = manager.Value('i', 0)


    def mayrequest(self, max_req):
        """
        Random request initiating method
        Parameters
        ----------
        max_req : int
            Maximum number of requests after which the program terminates.
        Returns
        -------
        None.
        """
        while self.my_requests.value < max_req:
            # sleep for random interval of time
            sleep(random.random())
            sleep(random.random())
            # randomly decide whether to request
            if random.randint(0, 1) == 1:
                if self.request(self.my_requests.value == (max_req - 1)):
                    self.my_requests.value += 1  # request counter increseases with every successful request


    def request(self, done):
        """
        Generates request if node not already in CS or requesting
        Parameters
        ----------
        done : bool
            Last request(True) or not(False).
        Returns
        -------
        bool
            Request successful(True) or not(False).
        """
        with self.token_lock:
            # if we're already in the cs, then request cannot be served
            if self.token.value == 1 or self.token.value == 2:
                return False
            else:
                self.token.value = 2
        with self.queue_lock:
            self.queue.append(self.id_.value)
            # if this is our last request, set the flag
            if done:
                self.request_done.value = 1
            # if the queue was previously empty, wake everyone
            if len(self.queue) == 1:
                for i in range(self.num_nodes):
                    self.watch.release()
        return True


    def cs(self):
        """
        Executes the critical section
        Returns
        -------
        None.
        """
        with self.token_lock:
            self.token.value = 1
        sleep(SLEEP_TIME)
        with self.queue_lock:
            self.queue.pop(0)  # remove itself from the queue
            for i in range(self.num_nodes):
                self.watch.release()  # wake all other threads
        with self.token_lock:
            self.token.value = 0


    def process_queue(self):
        """
        Processes the queue to enter critical section or grant access to child
        Returns
        -------
        None.
        """
        while True:
            self.watch.acquire()
            cs_go = False
            with self.queue_lock:
                if len(self.queue) > 0 and self.queue[0] == self.id_.value:
                    cs_go = True
            #print(self.id_.value, " Before Processing ... ", node)
            if cs_go:
                #print("Processing ...  %d", node.value)
                self.cs()
                if self.request_done.value == 1:
                    self.token.value = 3  # Set Status = Done if last request is served and terminate process
                    return


    def get_status(self):
        """
        Retrieves the status of the node
        Returns
        -------
        int
            Process ID.
        int
            Token value which determines the status of the node.
        integer list
            Current queue of the node.
        int
            Number of requests made by the process.
        """
        return (self.id_.value, self.token.value, self.queue, self.my_requests.value)


def init_processing(network, node):
    """
    Initiates the process_queue() for each of the nodes
    Parameters
    ----------
    network : List of Nodes
        List of all nodes in the graph along with the ring topology.
    node : int
        Node number whose tick() procedure is to be called.
    Returns
    -------
    None.
    """
    network[node].process_queue()

def init_request(network, node, max_req):
    """
    Initiates the free -> request -> cs -> done tick loop for
    each of the nodes
    Parameters
    ----------
    network : List of Nodes
        List of all nodes in the graph along with the ring topology.
    node : int
        Node number whose tick() procedure is to be called.
    max_req : int
        Maximum number of requests a node can make.
    Returns
    -------
    None.
    """
    network[node].mayrequest(max_req)


def print_status(neighbors):
    """
    Queries and prints the status of all the neighbors
    Parameters
    ----------
    neighbors : List of Nodes
        List of all nodes in the graph.
    Returns
    -------
    None.
    """
    STATUS_TEXT = ["Free", "IN CRITICAL SECTION", "Requesting", "Done"]
    while True:
        i = 0
        for neighbor in neighbors:
            stat = neighbor.get_status()
            print("Node %2d:      Status = %20s (Requests: %2d)" %
                  (stat[0], STATUS_TEXT[stat[1]], stat[3]),end='\t')
            if stat[1] == 1:
                print("Queue = ",stat[2])
            else:
                print("")
            i += 1
        print()
        sleep(UPDATE_TIME)

def main():
    num_nodes = int(input("enter nodes: "))  # number of nodes taken as argument
    manager = Manager()
    g_queue = manager.list()
    g_lock = manager.Lock()
    g_watch = manager.Semaphore()
    network = [Node(0, manager, g_queue, g_lock, g_watch, num_nodes)]  # adding first node in the network
    # adding the rest of the nodes in the network
    for i in range(num_nodes - 1):
        network.append(Node(i+1, manager, g_queue, g_lock, g_watch, num_nodes))

    # the nodes stop after this many total requests are made
    max_req = num_nodes

    # printer process initiation
    # the printer process is independent from the worker
    # pool which manages the nodes. it wakes up at UPDATE_TIME
    # interval, queries and prints the statuses of all the
    # nodes, and sleeps again
    printer = Process(target=print_status, args=(network,), daemon=True)
    printer.start()

    processes = []
    for i in range(num_nodes):
        processes.append(Process(target=init_processing, args=(network, i), daemon=True))
        #processes.append(Process(target=init_request,
        #                         args=(network, i, max_req),
        #                         daemon=True))
        processes[-1].start()


    # the worker pool
    # it contains one process for each of the node in the
    # network. each process gets assigned to perform the
    # free -> request -> cs loop for one node.
    jobPool = Pool(processes=len(network))
    jobPool.starmap(init_request, zip(repeat(network), range(num_nodes), repeat(max_req)))
    jobPool.close()
    jobPool.join()

    for p in processes:
        p.join()


if __name__ == "__main__":
    main()