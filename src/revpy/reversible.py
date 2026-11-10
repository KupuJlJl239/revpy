from types import FunctionType, CellType
import ast, inspect
from textwrap import dedent

from .base import ReversibleFunction, RevpyCompilationError, reversibility_assert
from .ast import ReversibleAstFunctionDef
from .compile import compile_functions

REVPY_ASSERT_NAME = reversibility_assert.__name__


###########################
###   FINAL DECORATOR   ###
###########################

def get_nonlocals(function) -> dict[str, CellType]:
    orig_freevars = function.__code__.co_freevars
    orig_cells = dict(zip(orig_freevars, function.__closure__ or ()))
    return orig_cells

def get_function_def(function):
    source = inspect.getsource(function)
    source = dedent(source)
    tree = ast.parse(source)  # возвращает Module
    return tree.body[0]


def reversible(function: FunctionType) -> ReversibleFunction:
    """
    Compiles a function into reversible function.

    - the first argument is considered the _input_
    - other arguments are considered the _parameters_ (i.e. captured values)
    - last line must be 'return \<variable name\>', and this variable is considered the _output_
    
    :param function: a function written with the revpy rules
    :return reversible_function: an instance of the class ReversibleFunction
    """
    f_def = get_function_def(function)
    globals = function.__globals__
    nonlocals = get_nonlocals(function) 

    if not REVPY_ASSERT_NAME is globals:
        nonlocals = nonlocals | {
            REVPY_ASSERT_NAME: CellType(reversibility_assert)
        }

    try:
        rf_def = ReversibleAstFunctionDef.from_ast(f_def)
    except RevpyCompilationError as e:
        raise RevpyCompilationError(e.msg) from None


    f, f_rev = compile_functions(
        [rf_def.to_ast(), rf_def.rev.to_ast()], 
        globals, nonlocals,
    )

    return ReversibleFunction(f=f, f_rev=f_rev)