
# Python has int, float, string and bool
def understanding_types():
    worst_language = "python"
    time = input("What time are you up at?: ")
    time = int(time)
    print("Using python to print the worst language:", worst_language, " @", time, end=" ;)\n")

def string_ops():
    should_i_freelance = "I DON't KnOw"
    print(should_i_freelance.lower())

def how_incompatible_strings():
    # Strings in python are ascii, so easier to process
    # but unnecessarily bad for  representing and process
    # multilingual characters
    println("ASCII strings, lololol!!!")

def most_important_for_dsa():
    # List of items
    x = [5,True, 'hello']
    x.append('world')
    print(x)
    # Tuples are immutable lists, similar to go-array
    x2 = (0,0,2,2)
    print(x2)

def iterating():
    for i in range(10,-1,-1):
        print(i)
    x = [3,5,6]
    for val in x:
        print(val)
    for idx in range(len(x)):
        print(x[idx])
    for idx, val in enumerate(x):
        print(idx,val)

def fast_querying():
    x = set()
    x2 = {3,5,6} # empty set can't bet created
    # using {} since that creates a dictionary
    print(x,x2, 4 in x)

    # Sets are the same syntax as hashmaps, 
    # what blasphemy is this
    x = {'name': 'dumbriyani'}
    print(x.values())
    print(list(x.keys()))
    # del x['hello'] - error if key doesn't exist
    for key, value in x.items():
        print(key, value)

def comprehensions():
    # Compressing a loop
    arr = [x for x in range(5) if x%2 == 1]
    print(arr)

# Named parameters, probaly come at the end of the signature
# but can probably be anywhere in caller
def outer_func(x,y,z=None):
    counter = 0
    def inner_func():
        counter = counter+1
    # Yes, golang copied multiple return from 
    # python
    return inner_func, 0

# kwargs - collect keyword args
# args - collect arguments
def func(*args, **kwargs):
    pass

def add(x,y):
    return x + y


x = [1,2,3,443]
# unpack operator, with a useless syntax
print(*x)
# unpacking in object takes two **
# and passed named parameters
print(add(**{'x':1, 'y': 2}))

def scoping(name):
    global x
    x = "noobda language"
    print(x)

def working_with_exceptions():
    try:
        x = 7/0
    except Exception as e:
        raise FileExistsError('This will create a stack trace')
    finally:
        print('finally close the file???')

def inline_functions():
    x = lambda x,y: x + y
    print(x(2,3))

def declarative_programming():
    x = [1,2,4,4,5,65,456,75676]
    # Why do we have global functions like map
    # instead of them existing on the specfic 
    # data structures like lists themselves
    mp = map(lambda i: i+2,x)
    print(list(mp))

def manipulating_strings():
    x = f'Is this the lowest point of my life, trying to learn {"PYTHON".lower}'

# iterating()
fast_querying()