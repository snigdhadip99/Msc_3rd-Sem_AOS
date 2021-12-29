from time import sleep
from multiprocessing import Pool, Process, Manager
import random
from itertools import repeat

# time spent in critical section, in seconds
SLEEP_TIME = 0.5
# interval to print the status of the nodes
UPDATE_TIME = 0.3

# request terminating value in local queue
SENTINEL = -3

FREE = 0
REQUESTING = 1
EXECUTING = 2
COMPLETED = 3

class Node:

    def __init__(self, manager, id_, nodes, parent_id):
        self.id_ = manager.Value('i', id_)
        self.queue_lock = manager.Lock()
        self.queue = manager.Queue()
        self.nodes = nodes
        self.parent = manager.Value('i', parent_id)
        self.semaphore = manager.Semaphore(0)
        self.status = manager.Value('i', FREE)
        self.status_lock = manager.Lock()
        self.my_requests = 0
        self.cs_requested = manager.Value('i', 0)
        self.dummy_queue = manager.list()


    def tick(self, max_req):  # main event loop
        """
        Local clock progression causing random request generation
        Parameters
        ----------
        max_req : int
            Maximum number of requests after which the program terminates
        Returns
        -------
        None.
        """
        while self.my_requests < max_req:
            # sleep for random interval of time
            sleep(random.random())
            sleep(random.random())
            sleep(random.random())
            # randomly decide whether to request
            maycall = random.randint(0, 2)
            if maycall:
                self.request()
                self.my_requests += 1


    def request(self):
        """
        Makes a new request. Enters Critical Section if it is root or
        waits till parent gives grant.
        Returns
        -------
        None.
        """
        with self.status_lock:
            if self.cs_requested.value == 1:
                return
            self.status.value = REQUESTING
            self.cs_requested.value = 1
        self.grant(self)


    def process_queue(self):
        """
        Processes the local queue to enter critical section or grant access to child
        Returns
        -------
        None.
        """
        while True:
            semaphore, node = self.queue.get()
            self.dummy_queue.pop(0)
            # we perform the checking outside of
            # the queue lock, because when we are
            # awaiting for a node to give us
            # back the control, we allow everybody
            # else to use request for control to us
            # otherwise check if we have a parent, and request for its permission
            if node == SENTINEL:
                #print(self, "recevied sentinel")
                self.status.value = COMPLETED
                return
            if self.parent.value != -1:
                parent = self.nodes[self.parent.value]
                parent.grant(self)
                self.semaphore.acquire()
                #print(self, "released by", self.parent.value)
            # make the node its parent, i.e. reverse the edge to make child new root
            if node == self.id_.value:
                #print(self, "executing cs")
                self.critical_section()
                #print(self, "cs complete")
            else:
                with self.status_lock:
                    self.parent.value = node
                # release the node's semaphore to allow
                # it to execute critical section
                #print(self, "releasing", node)
                semaphore.release()


    def grant(self, node):
        """
        Add requestinf node to local queue
        Parameters
        ----------
        node : Node
            Reference to the node which is requesting token access
        Returns
        -------
        None.
        """
        # we use this variable to wait for grant
        # outside of all locks, so they can be
        # acquired by other processes
        #print(self, "asked by", node)
        # add the node to our queue
        with self.queue_lock:
            self.queue.put((node.semaphore, node.id_.value))
            self.dummy_queue.append(node.id_.value)


    def critical_section(self):
        """
        Executes the critical section
        Returns
        -------
        None
        """
        with self.status_lock:
            self.status.value = EXECUTING
            self.parent.value = -1
        sleep(SLEEP_TIME)
        #print(self, "awake")
        with self.status_lock:
            self.status.value = FREE
            self.cs_requested.value = 0


    def get_status(self):
        """
        Retrieves the status of the node
        Returns
        -------
        int
            execution status of the node
        int
            current parent of the node
        String
            Current request_queue of the node
        """
        return (self.status.value, self.parent.value, self.dummy_queue)


    def __repr__(self):
        """
        Returns a representation of Node object
        Returns
        -------
        String
            String representation of Node object
        """
        return "[Node %d]" % self.id_.value


STATUS_TEXT = ["free", "wait", "crit", "done"]

def print_tree_rec(root, tree, neighbors, tab=0):
    """
    Display the current logical tree structure of the network
    Parameters
    ----------
    root : int
        Root of the tree currently
    tree : List of lists
        The tree represented as list of list
        where each list represents the list of children
    neighbors : List of Nodes
        List of all nodes in the graph
    tab : int, optional
        Amount of space wich increases with level of tree. The default is 0
    Returns
    -------
    None
    """
    for _ in range(tab):
        print("   ", end='')
    print("|-", root, end=' ')
    status = neighbors[root].get_status()
    print("(", STATUS_TEXT[status[0]], ",", "queue:", status[2], ")")
    for r in tree[root]:
        print_tree_rec(r, tree, neighbors, tab + 1)


def print_status(neighbors):
    """
    Queries and prints the status of all the neighbors
    Parameters
    ----------
    neighbors : List of Nodes
        List of all nodes in the graph
    Returns
    -------
    None
    """
    l = len(neighbors)
    while True:
        i = 0
        tree = [[] for _ in range(l)]
        root = 0
        for i, neighbor in enumerate(neighbors):
            if neighbor.parent.value == -1:
                root = i
            else:
                tree[neighbor.parent.value].append(i)
        print_tree_rec(root, tree, neighbors)
        print()
        sleep(UPDATE_TIME)  # repeat printing process at regular interval


def start_tick(neighbors, node, max_req):
    """
    Initiates the free -> request -> cs tick loop for
    each of the nodes
    Parameters
    ----------
    neighbors : List of Nodes
        List of all nodes in the graph
    node : Node
        Node object whose tick() procedure is to be called
    max_req : int
        Maximum number of requests a node can make
    Returns
    -------
    None
    """
    neighbors[node].tick(max_req)


def start_process_queue(neighbors, node):
    """
    Initiates the process_queue() for each of the nodes
    Parameters
    ----------
    neighbors : List of Nodes
        List of all nodes in the graph
    node : Node
        Node object whose process_queue() procedure is to be called
    Returns
    -------
    None.
    """
    neighbors[node].process_queue()


def main():
    import sys
    try:
        num_nodes = int(input("Enter number of nodes: "))
        if num_nodes < 2:
            raise Exception("error")
    except:
        print("[Error] Invalid number of nodes passed as argument!")
        return

    # mp manager to acquire shared locks
    manager = Manager()

    # initialization of all the neighbors
    neighbors = []
    for i in range(num_nodes):
        if i == 0:
            parent_id = -1
        else:
            parent_id = random.randint(0, i - 1)  # generate random parent from exissting nodes
        neighbors.append(Node(manager, i, neighbors, parent_id))  # append new node to the graph

    # the nodes stop after this many total requests are made
    max_req = num_nodes

    # printer process initiation
    # the printer process is independent from the worker
    # pool which manages the nodes. it wakes up at UPDATE_TIME
    # interval, queries and prints the statuses of all the
    # nodes, and sleeps again
    printer = Process(target=print_status, args=(neighbors,), daemon=True)
    printer.start()

    processes = []
    for i in range(num_nodes):
        processes.append(Process(target=start_process_queue, args=(neighbors, i), daemon=True))
        processes[-1].start()

    # the worker pool
    # it contains one process for each of the node in the
    # network. each process gets assigned to perform the
    # free -> request -> cs loop for one node.
    jobPool = Pool(processes=len(neighbors))
    jobPool.starmap(start_tick, zip(repeat(neighbors), range(len(neighbors)), repeat(max_req)))
    jobPool.close()
    jobPool.join()
    # request done
    for node in neighbors:
        with node.queue_lock:
            node.queue.put((None, SENTINEL))
            node.dummy_queue.append(SENTINEL)

    for p in processes:
        p.join()


if __name__ == "__main__":
    main()