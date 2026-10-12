# They don't even have consistent naming 
## in their own libraries
from collections import Counter, namedtuple, defaultdict, deque
from itertools import product, permutations
import heapq
from bisect import bisect_left, bisect_right

# For stacks, we use lists only

def exploring():
    a ="aaabbbb"
    my_counter = Counter(a)
    print(my_counter)
    print(my_counter.elements(), my_counter.most_common())

def naming_tuples():
    Point = namedtuple('Point', 'x,y')
    pt = Point(1,-4)
    print(pt.x,pt.y)

def DictInspiredByGo():
    ordered_dict =  defaultdict(int)
    d['a'] = 1
    d['b'] = 2
    print(d['a'], d['c'])

def SomethingNotPresentInIndia():
    d = deque()
    d.append(2)
    d.appendleft(1)

def pile_of_dirt():
    # Do they think outside of lists
    # as pythonistas
    heap = [3,1,5,7]
    # Min heap by default, negate it for
    # creating a max heap (why does it have
    # to go against every other programming language)
    heapq.heapify(heap)
    heapq.heappush(heap,2)
    smallest = heapq.heappop(heap)

def multiplication():
    a = [1,2]
    b = [3,4]
    prod = product(a,b)
    print(list(prod))

def hiladenge():
    a = [ 1,2,3]
    perm = permutations(a)
    print(list(perm))

def search_logarithmic():
    arr = [1,2,2,3,5,0]
    print(bisect_left(arr,2))
    print(bisect_right(arr,2))

def sorting():
    points2D = [(1,2), (15,1), (5,-1), (10,4)]
    prints2D_sorted = sorted(points2D, key=lambda x: x[1])
    print(points2D)
    print(points2D_sorted)

# Creating custom exceptions is too easy
class ValueTooHighError(Exception):
    pass


class ValueTooSmallError(Exception):
    def __init__(self, message, value):
        self.message = message
        self.value = value

def test_value(x):
    if x > 100:
        raise ValueTooHighError('value if too high')
    if x < 5:
        raise ValueTooSmallError('value is too small', x)

try:
    test_value(200)
except ValueTooHighError as e:
    print(e)
except ValueTooSmallError as e:
    print(e.message, e.value)

exploring()