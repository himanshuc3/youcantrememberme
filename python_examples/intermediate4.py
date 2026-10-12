# Generators -> possibly useful for streams
def mygenerator():
    yield 1
    yield 2
    yield 3

def fibonacci(limit):
    a,b = 0,1

    while a < limit:
        yield a
        a,b = b,a+b

g = mygenerator()

value = next(g)
print(value)

fib = fibonacci(30)
for i in fib:
    print(i)