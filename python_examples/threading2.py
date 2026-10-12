# Thread is an entity within a process,
# so multiple threads can be created within a process
# to improve on the inter-process communication
# Threads are useful with I/O bound tasks, not with cpu bound 
# since only 1 thread at a time is running
# Referencing count for garbage collection leads to unsafe memory management
# in CPython implementation
from threading import Thread, Lock
import os
from queue import Queue
import time

database_value = 0

def increase(lock):
    global database_value

    # lock.acquire()
    with lock:
        local_copy = database_value

        # processing
        local_copy += 1
        time.sleep(0.1)

        database_value = local_copy
    # lock.release()



if __name__ == "__main__":
    print("start value", database_value)
    lock = Lock()
    # Threading works similarly
    # This is a tuple and to initiate it like that
    # we need to add a comma
    thread1 = Thread(target=increase, args= (lock,))
    thread2 = Thread(target=increase, args= (lock,))


    thread1.start()
    thread2.start()

    thread1.join()
    thread2.join()
    print('end value', database_value)
    print('end main')