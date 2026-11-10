import ast, random, linecache
from types import CellType, FunctionType
from typing import Iterable, Any


FAKE_FILENAME_PREFIX = "<revpy-dynamic-compilation>"
FACTORY_NAME = "__revpy_compile_factory__"


def ast_factory_def(function_defs: list[ast.FunctionDef], nonlocal_names: Iterable[str]):
    return ast.FunctionDef(
        name=FACTORY_NAME,
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg=n) for n in nonlocal_names],
            kwonlyargs=[], kw_defaults=[], defaults=[],
        ),
        body=function_defs + [
            ast.Return(
                value = ast.Tuple(
                    elts=[
                        ast.Name(id=f_def.name, ctx=ast.Load()) for f_def in function_defs
                    ],
                    ctx=ast.Load(),
                ),
            )
        ],
        decorator_list=[],
    )

def generate_factory_src(function_defs: list[ast.FunctionDef], nonlocal_names: Iterable[str]):
    """
    Constructs such code:
    
    def {FACTORY_NAME}(a_1, ..., a_n):
        def f_1(...):
            ...

        ...

        def f_k(...):
            ...
        
        return f_1, ..., f_k

    Here:
    -  a_1, ..., a_n are nonlocal_names
    -  f_1, ..., f_k are function_defs 
    """
    factory_def = ast_factory_def(function_defs, nonlocal_names)
    module = ast.Module(body=[factory_def], type_ignores=[])
    ast.fix_missing_locations(module)
    return ast.unparse(module)


def change_env(f: FunctionType, globals: dict, nonlocals: dict[str, CellType]):
    closure = tuple(nonlocals[name] for name in f.__code__.co_freevars) or None
    new_f = FunctionType(
        code=f.__code__,
        globals=globals,
        name=f.__name__,
        closure=closure
    )
    new_f.__defaults__ = f.__defaults__
    new_f.__kwdefaults__ = f.__kwdefaults__
    return new_f


def generate_fake_filename():
    while True:
        fake_filename = f"<{FAKE_FILENAME_PREFIX}-{random.randint(0, 100000000000)}>"
        if not fake_filename in linecache.cache:
            return fake_filename


def compile_functions(
    function_defs: list[ast.FunctionDef],
    globals: dict[str, Any],
    nonlocals: dict[str, CellType],
) -> list[FunctionType]:

    # generate source code and filename
    src = generate_factory_src(function_defs, nonlocals.keys())
    file = generate_fake_filename()

    # compile this file and store it's source to linecache
    code = compile(src, file, "exec")
    lines = [line + "\n" for line in src.splitlines()]
    linecache.cache[file] = (len(src), None, lines, file)

    # run that file and get factory function
    g = {}
    exec(code, g)
    factory = g[FACTORY_NAME]

    # set factory function to appropriate environment
    factory = change_env(factory, globals, nonlocals={})

    # run factory function and get our compiled functions
    factory_kwargs = {k: v.cell_contents for k, v in nonlocals.items()}
    functions: tuple[FunctionType] = factory(**factory_kwargs)

    # set these functions to appropriate environment
    functions = [change_env(f, globals, nonlocals) for f in functions]
    return functions