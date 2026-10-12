import json
import functools



def serialization():

    person = {"name": "Dyuti", "age": 30, "city": "Goohati"}

    # Serialization
    personJSON = json.dumps(person, indent = 4)
    print(personJSON)
    # json.loads for deserialization 
    with open('person.json', 'w') as file:
        json.dump(person, file)

# Optionally we can extend from JSONEncoder 
class User:
    def __init__(self, name, age):
        self.name = name
        self.age = age

user = User('mitraaa', 30.1)

def encode_user(o):
    if isinstance(o,User):
        return {'name': o.name, 'age': o.age, o.__class__.__name__: True}
    else:
        raise TypeError('Object is not serializable')

# This can also work as a decorator
class CountCalls:
    def __init__(self,func):
        self.func = func
        self.num_calls =0

    def __call__(self, *args, **kwargs):
        print('Hi there')
        self.num_calls += 1

def start_end_decorator(func):

    # Used to preserve context like og func name
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print('Start')
        func(*args,**kwargs)
        print('End')
    return wrapper

# There are function and class decorators
# It seems like syntactic sugar for HoF
# Decorators can be stacked
@CountCalls
@start_end_decorator
def dosomething(x,y):
    print(x+y)

serialization()

userJSON = json.dumps(user, default=encode_user)
print(userJSON)