# Thread is an entity within a process,
# so multiple threads can be created within a process
# to improve on the inter-process communication
# Threads are useful with I/O bound tasks, not with cpu bound 
# since only 1 thread at a time is running
# Referencing count for garbage collection leads to unsafe memory management
# in CPython implementation
from multiprocessing import Process
from threading import Thread
import os
import time


def square_numbers():
    for i in range(100):
        i*i
        time.sleep(0.1)

# Threading works similarly
processes = []
num_processes = os.cpu_count()



for i in range(num_processes):
    p = Process(target=square_numbers)
    processes.append(p)

for p in processes:
    p.start()

# Blocking the main thread until all processes finish
# Done using signals in golang
for p in processes:
    p.join()