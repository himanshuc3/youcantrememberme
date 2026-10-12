import copy 

def example():
    # Mutable references - objects
    # Immutable values - primitives like int
    # strings wouldn't be mutated and needs to 
    # be returned
    # Abismal syntax
    zeros = [0] * 10
    himanshu = "rules"*10
    print(zeros," Himanshu :", himanshu)
    # Dereference operator in other langaugages (*)
    # is used for all kinds of operations but creating pointers

def copying():
    # Since everything by default is a reference
    # do we even save anything on the stack?
    org = [1,2,3]
    cpy = org # reference copy
    cpy[2] = 10 # changes org?
    print(org, cpy)
    # Also has a deep copy alternative
    cpy2 = copy.copy(org)
    cpy2[2] = 11
    print(org, cpy, cpy2)

# Didn't have enough energy to record syntax for 
# context managers, but they're mostly used as 
# syntactic sugar over manual construction and deconstruction
# To create user contexts, define enter and exit hooks in a class


copying()