from time import sleep
from multiprocessing import Pool, Process, Manager
import random
from itertools import repeat
import sys

CONTROLLER_SLEEP = 0.2

class Resource:

    def __init__(self, m, i):
        self.sem = m.Semaphore()
        self.id_ = i
        self.acquired_by = m.Value('i', -1)


    def acquire(self, node):
        """
        Acquires the resource object
        Parameters
        ----------
        node : Node
            Node object requesting for the resource
        Returns
        -------
        None.
        """
        node.print("Trying to acquire R" + str(self.id_),
                   "[Currently acquired by " + str(self.acquired_by.value) + "]")
        self.sem.acquire()
        self.acquired_by.value = node.id_
        node.print("Acquired R" + str(self.id_))


    def release(self, node):
        """
        Releases the resource object once served
        Parameters
        ----------
        node : Node
            Node object requesting for the resource
        Returns
        -------
        None.
        """
        node.print("Released R" + str(self.id_))
        self.sem.release()



class Node:

    def __init__(self, id_, res_tab, res_tab_lock, num_res, res_sems):
        # resource table is (resource x process) bipolar table where
        # -1 in a cell denotes resource Ri is being waited on by process
        # Pj. +1 denotes it is acquired by Pj. This is a global table,
        # and is accessed and modified by all the nodes in the network.
        self.resource_table = res_tab
        # lock for the table
        self.res_tab_lock = res_tab_lock
        self.id_ = id_
        self.num_resource = num_res
        # semaphores for the nodes to wait on resources
        self.resource_semaphores = res_sems
        self.my_requests = 0


    def fire(self, max_req, global_sema):
        """
        Generate new resource requests
        Parameters
        ----------
        max_req : int
            Maximum number of requests a node can make.
        global_sema : Semaphore
            Semaphore to check if further requests are possible.
        Returns
        -------
        None.
        """
        while self.my_requests < max_req:
            if random.randint(0, 1) == 1:
                self.request()
                self.my_requests += 1

            sleep(random.random())
            sleep(random.random())
            sleep(random.random())
        self.print("Maximum Requests served. Exiting ...")
        global_sema.release()  # Release semaphore if current node has reached maximum requests


    def request(self):
        """
        Request resources and utilise them
        Returns
        -------
        None.
        """
        num_res = random.randint(1, self.num_resource)  # number f resources required
        resources = random.sample(range(self.num_resource), num_res)  # which resources are required
        sleep_time = random.random() + random.random()
        with self.res_tab_lock:
            self.print("Resource list generated:", self.get_remaining_resources(resources))
            for res in resources:
                self.resource_table[res][self.id_] = -1  # update resource status table
        i = 0  # number of resources held
        for res in resources:
            self.resource_semaphores[res].acquire(self)
            with self.res_tab_lock:
                self.resource_table[res][self.id_] = 1
            self.print("Remaining", self.get_remaining_resources(resources[i+1:]))
            i += 1
        # All resources accessed, now utilise
        self.execute(resources, sleep_time)


    def get_remaining_resources(self, res):
        """
        Tells the resources that have been requested but not yet allocated to requesting process
        Also mentions which process currently holds the requested resources
        Parameters
        ----------
        res : List
            List of Resources.
        Returns
        -------
        res_acq : List
            List of strings mentioning which resouce is held by whom.
        """
        res_acq = {}
        for r in res:
            res_acq["R" + str(r)] = self.resource_semaphores[r].acquired_by.value
        return res_acq


    def print(self, *args):
        """
        Displays passed information along with id of the node
        Parameters
        ----------
        *args : Pointer
            Variable number of arguments.
        Returns
        -------
        None.
        """
        print("[Node %3d] " % self.id_, *args)



    def execute(self, resources, sleep_time):
        """
        Utilise the requested resources
        Parameters
        ----------
        resources : List
            List of all the resources that are requested.
        sleep_time : int
            Time to execute.
        Returns
        -------
        None.
        """
        sleep(sleep_time)
        for res in resources:
            with self.res_tab_lock:
                self.resource_table[res][self.id_] = 0
            self.resource_semaphores[res].release(self)


def fire_node(nodes, num, max_req, global_sema):
    """
    Initiates the resource requests for each of the nodes
    Parameters
    ----------
    nodes : List of Nodes
        List of all nodes in the system.
    num : int
        Number of nodes in the system.
    max_req : int
        Maximum number of requests a node can make.
    global_sema : Semaphore
        Semaphore to check if further requests are possible.
    Returns
    -------
    None.
    """
    nodes[num].fire(max_req, global_sema)


def print_path(path, vertex, visited=set()):
    """
    Displays the cycle recursively if deadlock is present
    Parameters
    ----------
    path : List
        List of nodes falling the cycle.
    vertex : int
        ID of the last node in the cycle.
    visited : Set, optional
        Set of vertices that are visited in the path. The default is set().
    Returns
    -------
    None.
    """
    if path[vertex] == -1:
        print(vertex, end=' ')
    else:
        if vertex not in visited:
            visited.add(vertex)
            print_path(path, path[vertex], visited)
            print("-->", end=' ')
        print(vertex, end=' ')


def dfs(adj, vertex, unvisited, path, stack=[]):
    """
    DFS algorithm to check if WFG contains cycle
    Parameters
    ----------
    adj : matrix
        Adjacency matrix of WFG.
    vertex : int
        ID of vertex from which DFS will be initiated.
    unvisited : List
        List of vertices not yet visited by DFS algorithm.
    path : List
        List of vertices falling in the path of the cycle.
    stack : List, optional
        Stack to be used by the DFS algorithm. The default is [].
    Returns
    -------
    Boolean
        True if DFS algorithm completes successfully, False otehrwise.
    int
        If DFS is usuccessful then ID of the vertex from where cycle
        is generated, None otehrwise.
    """
    #print("at", vertex)
    if vertex in unvisited:
        unvisited.remove(vertex)
    if vertex in stack:
        return False, vertex  # cycle found
    stack.append(vertex)
    for v in adj[vertex]:
        path[v] = vertex
        res, v = dfs(adj, v, unvisited, path, stack)
        if not res:
            return res, v
    stack.pop()
    return True, None


def check_for_deadlock(res_tab, res_tab_lock, num_nodes, global_sema):
    """
    Controller module responsible for detecting deadlock
    Parameters
    ----------
    res_tab : 2-d List
        Resource Status Table.
    res_tab_lock : Lock
        Lock to be used while accessing the resource status table.
    num_nodes : int
        Number of nodes in the system.
    global_sema : Semaphore
        Semaphore to check if further requests are possible.
    Returns
    -------
    None.
    """
    while True:
        print("[Controller] Starting deadlock detection..")
        adjacency_matrix = [[] for _ in range(num_nodes)]
        with res_tab_lock:
            for row in res_tab:
                to_vertex = [idx for idx in range(num_nodes) if row[idx] == 1]
                if len(to_vertex) == 0:
                    continue
                to_vertex = to_vertex[0]
                from_vertices = [idx for idx in range(num_nodes) if row[idx] == -1]
                for v in from_vertices:
                    if to_vertex not in adjacency_matrix[v]:
                        adjacency_matrix[v].append(to_vertex)
        # print(adjacency_matrix)
        # dfs
        unvisited = list(range(num_nodes))
        cycle = False
        path, last_vertex = None, None
        while not cycle and len(unvisited) > 0:
            u = unvisited.pop(0)
            path = [-1] * num_nodes
            c, last_vertex = dfs(adjacency_matrix, u, unvisited, path)
            cycle = cycle or not c
        if cycle:
            print("[Controller] Deadlock detected! System is UNSAFE!")
            print("[Controller] The cycle is: ", end="")
            #print(path)
            print_path(path, last_vertex)
            print()
            #killEvent.set()with global_sema_lock:
            for i in range(num_nodes):  # release all as no other requests can be granted
                global_sema.release()
            return
        else:
            print("[Controller] No deadlock detected!")
        sleep(CONTROLLER_SLEEP)



def main():
    m = Manager()
    num_process = int(input("Enter no of nodes: "))
    num_resource = int(input("Enter no of resources: "))
    res_tab = [m.list([0] * num_process) for _ in range(num_resource)]
    res_tab = m.list(res_tab)
    res_tab_lock = m.Lock()
    res_sems = m.list([Resource(m, i) for i in range(num_resource)])
    global_sema = m.Semaphore(0)

    nodes = [Node(i, res_tab, res_tab_lock, num_resource, res_sems) for i in range(num_process)]

    # the nodes stop after this many total requests are made
    max_req = num_process

    #killEvent = m.Event()
    # controller process
    controller = Process(target=check_for_deadlock, args=(res_tab, res_tab_lock, num_process, global_sema), daemon=True)
    controller.start()

    '''
    processes = []
    for i in range(num_process):
        processes.append(Process(target=check_for_deadlock, args=(), daemon=True))
        processes[-1].start()
        '''
    # the worker pool
    # it contains one process for each of the node in the
    # network. each process gets assigned to perform the
    # free -> request -> cs loop for one node.
    jobPool = Pool(processes=len(nodes))
    jobPool.starmap_async(fire_node, zip(repeat(nodes), range(len(nodes)), repeat(max_req), repeat(global_sema)))
    #jobPool.close()
    # request done

    for _ in range(num_process):
        global_sema.acquire()
    #killEvent.wait()
    jobPool.terminate()
    #controller.close()
    controller.terminate()

    #controller.join()

    '''
    for node in nodes:
        with node.queue_lock:
            node.queue.put((None, SENTINEL))
            node.dummy_queue.append(SENTINEL)
    for p in processes:
        p.join()
        '''
if __name__ == "__main__":
    main()