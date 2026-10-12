# Alternative to threading2

# Thread is an entity within a process,
# so multiple threads can be created within a process
# to improve on the inter-process communication
# Threads are useful with I/O bound tasks, not with cpu bound 
# since only 1 thread at a time is running
# Referencing count for garbage collection leads to unsafe memory management
# in CPython implementation
from threading import Thread, current_thread, Lock
from queue import Queue

database_value = 0

# busy waiting wouldn't be a problem here???
def worker(q, lock):
   while True:
    value = q.get()
    with lock:
        # processing
        print(f'in {current_thread().name} got {value}')
    q.task_done()




if __name__ == "__main__":
    q = Queue()
    lock = Lock()
    num_threads = 10


    for i in range(num_threads):
       thread = Thread(target=worker, args=(q,lock))
       thread.daemon = True
       thread.start()

    for i in range(1,21):
       q.put(i)

    q.join()

    print('end main')

    