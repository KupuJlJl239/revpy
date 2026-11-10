from dataclasses import dataclass
from inspect import getsource
from textwrap import dedent



@dataclass
class RevpyCompilationError(Exception):
    """
    Base class for reversibility errors at the code analysis stage.
    """
    msg: str
    # pass


class ReversibilityError(Exception):
    """
    Base class for reversibility errors at runtime.
    """
    pass


def reversibility_assert(condition, message=''):
    """
    Raises ReversibilityError exception if <condition> is False.

    @reversible uses this functions for reversibility checks in if/fi and while/elihw.

    Use it for reversibility checks in partially reversible functions.
    Though you can use ordinary 'assert' or anything else instead of it.
    
    :param condition: condition that must be True
    :param message: error message describing what went wrong if condition is False
    """
    if not condition:
        raise ReversibilityError(message)



class ReversibleFunction:
    """
    A wrapper class over a pair of functions f and f_rev, combining them into a single reversible function.

    The first argument of the functions is considered the value being destroyed, the rest -- parameters (which are not destroyed).
    """
    def __init__(self, f, f_rev, args=(), kwargs=None):
        self.f = f
        self.f_rev = f_rev

        self.args = args
        self.kwargs = kwargs if kwargs is not None else {}

    def __call__(self, *args, **kwargs):
        return ReversibleFunction(self.f, self.f_rev, self.args + args, self.kwargs | kwargs)

    @property
    def rev(self):
        return ReversibleFunction(self.f_rev, self.f, self.args, self.kwargs)
    
    def __getitem__(self, input):
        return self.f(input, *self.args, **self.kwargs)
    
    @property
    def src(self):
        return dedent(getsource(self.f))



def fi(reverse_condition: bool):
    """
    Stub function for the if construct

    if condition:
        ...
    else:
        ...
    fi(reverse_condition)
    
    :param reverse_condition: the condition that must be true at the moment of exiting the if branch and false at the moment of exiting the else branch. If fi is not provided, then by default reverse_condition = condition.
    """
    pass


def elihw(reverse_condition: bool):
    """
    Stub function for the while construct

    while condition:
        ...
    elihw(reverse_condition)
    
    :param reverse_condition: the condition that must be false at the moment of entering the loop and true every time the end of the loop is reached
    :type reverse_condition: bool
    """
    pass