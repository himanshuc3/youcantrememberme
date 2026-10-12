from multiprocessing import Process, Value, Array, Lock
import time
# Processes aren't allowed to share memory, so we 
# specifically create data to be shared
def add_100(number, lock):
    for i in range(100):
        time.sleep(0.1)
        with lock:
            number.value += 1

if __name__ == "__main__":
    lock = Lock()
    shared_number = Value('i', 0)
    print('Number at beginning is', shared_number.value)

    p1 = Process(target=add_100, args=(shared_number,lock))
    p2 = Process(target=add_100, args=(shared_number,lock))

    p1.start()
    p2.start()

    p1.join()
    p2.join()


    print('number at end is', shared_number.value)