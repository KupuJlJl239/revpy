from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Any
from copy import deepcopy
import ast, inspect
import types
import sys



__all__ = [
    'ReversibleFunction',
    'reversible',

    'fi','elihw',

    'ReversibilityError',
    'reversibility_assert',
    'RevpyCompilationError',
]


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





class ReversibleFunction:
    """
    Класс-обёртка над парой функций f и f_rev, объединяющий их в одну обратимую функцию.

    Первый аргумент функций считается уничтожаемым значением, остальные -- параметрами (которые не уничтожаются).
    """
    def __init__(self, f, f_rev, args=(), kwargs=None):
        self.f = f
        self.f_rev = f_rev

        self.args = args
        self.kwargs = kwargs if kwargs is not None else {}
        self.__signature__ = inspect.signature(f)

    def __call__(self, *args, **kwargs):
        return ReversibleFunction(self.f, self.f_rev, self.args + args, self.kwargs | kwargs)

    @property
    def rev(self):
        return ReversibleFunction(self.f_rev, self.f, self.args, self.kwargs)
    
    def __getitem__(self, input):
        return self.f(input, *self.args, **self.kwargs)
    
    @property
    def src(self):
        return self.f.src



@dataclass
class RevpyCompilationError(Exception):
    """
    Base class for reversibility errors at runtime.
    """
    msg: str


class ReversibilityError(Exception):
    """
    Base class for reversibility errors at the code analysis stage.
    """
    pass


def reversibility_assert(condition, message=''):
    """
    Кидает исключение ReversibilityError в случае, если condition ложно.

    Используйте, для проверок условий обратимости. 
    Это исключительно вспомогательная функция, можно использовать что угодно вместо неё.
    
    :param condition: Description
    :param message: Description
    """
    if not condition:
        raise ReversibilityError(message)



revpy_assert_name = 'reversibility_assert'


############################
###   LIFETIMES CHECKS   ###
############################

@dataclass
class VariableSideUsage:
    name: str
    exists: bool
    usage: str

    def match(self, other: VariableSideUsage) -> None:
        assert self.name == other.name
        if self.exists != other.exists:
            raise RevpyCompilationError(f"Lifetime error: variable '{self.name}'\n\t--> {self.usage}\n\t--> {other.usage} ")

@dataclass
class VariableUsage:
    start: VariableSideUsage
    end: VariableSideUsage 
    own: bool

    def __add__(self, other: VariableUsage) -> VariableUsage:
        self.end.match(other.start)
        return VariableUsage(self.start, other.end, self.own | other.own)
    
    def __or__(self, other: VariableUsage) -> VariableUsage:
        self.start.match(other.start)
        self.end.match(other.end)
        return VariableUsage(self.start, other.end, self.own | other.own)
    
    @property
    def rev(self):
        return VariableUsage(start=self.end, end=self.start, own=self.own)
    
    def check(self) -> VariableUsage:
        assert self.start.name == self.end.name
        if self.start.exists != self.end.exists:
            raise RevpyCompilationError(f"Lifetime error: variable '{self.start.name}' must both exist or both not exist\n\t--> {self.start.usage}\n\t--> {self.end.usage} ")
        return self



def unite_dicts(A, B, unary_op, binary_op):
    common = {k: binary_op(A[k], B[k]) for k in A.keys() & B.keys()}
    non_common = {k: unary_op(v) for k, v in (A | B).items() if not k in (A.keys() & B.keys())}
    return common | non_common

@dataclass
class Signature:
    dct: dict[str, VariableUsage]

    def __add__(self, other: Signature) -> Signature:
        return Signature(unite_dicts(self.dct, other.dct, unary_op=lambda x: x, binary_op=VariableUsage.__add__))
    
    def __or__(self, other: Signature) -> Signature:
        return Signature(unite_dicts(self.dct, other.dct, unary_op=VariableUsage.check, binary_op=VariableUsage.__or__))
    
    @staticmethod
    def from_line(input: Iterable[str], output: Iterable[str], capture: Iterable[str], line: str) -> Signature:
        IN = set(input)
        OUT = set(output)
        if len(IN) != len(input):
            raise RevpyCompilationError(f"Some destroyed names repeat! Line:\n{line}\n")
        if len(OUT) != len(output):
            raise RevpyCompilationError(f"Some created names repeat! Line:\n{line}\n")
        C = set(capture)
        if not C.isdisjoint(IN):
            raise RevpyCompilationError(f"Some names are destroyed and captured at the same time: {C & IN}! Line:\n{line}\n")
        if not C.isdisjoint(OUT):
            raise RevpyCompilationError(f"Some names are created and captured at the same time: {C & OUT}! Line:\n{line}\n")\
        
        return Signature({
            k: VariableUsage(
                start=VariableSideUsage(name=k, exists=k in IN | C, usage=line),
                end=VariableSideUsage(name=k, exists=k in OUT | C, usage=line),
                own=k not in C
            ) 
            for k in IN | OUT | C   # k -- имя переменной
        })
    
    @property
    def rev(self):
        return Signature({k: v.rev for k, v in self.dct.items()})
    
    @property
    def names_input(self):
        return set([k for k, v in self.dct.items()  if v.start.exists and v.own])
    
    @property
    def names_output(self):
        return set([k for k, v in self.dct.items()  if v.end.exists and v.own])
    
    @property
    def names_capture(self):
        return set([k for k, v in self.dct.items() if not v.own])
    
    @property
    def names_local(self):
        return set([k for k, v in self.dct.items()  if v.own])
    
    @property
    def names_all(self):
        return set([k for k, v in self.dct.items() ])







#####################################
###   AST PARSING AND REVERTING   ###
#####################################



class ReversibleAstExpr:
    """ 
    Некоторый кусок обратимого кода.
    """


    # def _to_ast(self):
    def to_ast(self, *args, **kwargs) -> ast.AST | list[ast.AST]:
        """
        Возвращает ast-представление прямого куска кода.
        """
        return ast.fix_missing_locations(self._to_ast(*args, **kwargs))
    
    @property
    def rev(self) -> ReversibleAstExpr:
        """
        Возвращает обратный кусок кода.
        """
        raise NotImplementedError()
    
    @staticmethod
    def from_ast(tree: ast.AST) -> ReversibleAstExpr:
        """
        Парсит обычный ast в своё внутреннее представление.
        """
        raise NotImplementedError()
    
    @property
    def signature(self) -> Signature:
        """
        Возвращает сигнатуру этого куска обратимого кода.
        """
        return self._signature


def ast_not(condition: ast.AST) -> ast.AST:
    return ast.UnaryOp(op=ast.Not(), operand=condition)




def ast_reversibility_assert(condition: ast.AST) -> ast.AST:
    message = f"reversibility_assert is False: '{ast.unparse(condition)}'"
    return ast.Expr(
        value=ast.Call(
            func=ast.Name(id=revpy_assert_name, ctx=ast.Load()),
            args=[
                condition, 
                ast.Constant(value=message)
            ],
            keywords=[]
        )
    )


def ast_is_none(value: ast.AST) -> ast.AST:
    return ast.Compare(
        left=value,
        ops=[ast.Is()],
        comparators=[ast.Constant(value=None)]
    )



    
def parse_ast_args(args) -> set[str]:
    if isinstance(args, ast.Name):
        assert isinstance(args.id, str)
        return set([args.id])
    elif isinstance(args, ast.Tuple) or isinstance(args, ast.List):
        res = set()
        for it in args.elts:
            A = parse_ast_args(it)
            if not res.isdisjoint(A):
                raise RevpyCompilationError(f"Arguments of reversible function must not contain repeated names! '{ast.unparse(args)}'")
            res = res | A
        return res
    else:
        raise RevpyCompilationError(f"Arguments of reversible function must be only pure names, but got: '{ast.unparse(args)}'")
    
def parse_ast_args_with_none(args) -> set[str] | None:
    if isinstance(args, ast.Constant):
        if args.value is not None:
            raise RevpyCompilationError(f"Got not-None constant as argument of reversible function: '{args.value}'")
        return set()
    else:
        return parse_ast_args(args)
    
def parse_ast_names(tree: ast.AST) -> set[str]:
    return set([item.id for item in ast.walk(tree) if isinstance(item, ast.Name)])

@dataclass
class ReversibleAstArguments:
    names: set[str]
    tree: ast.AST

    @staticmethod
    def from_ast(tree: ast.AST | None) -> ReversibleAstArguments:
        if tree is None:
            names = set()
            tree = ast.Constant(value=None)
        else:
            names = parse_ast_args_with_none(tree)
            tree = tree
        return ReversibleAstArguments(names, tree)
    
    def to_ast(self, ctx: ast.expr_context) -> ast.expr:
        tree = deepcopy(self.tree)
        for it in ast.walk(tree):
            if isinstance(it, ast.AST):
                it.ctx = ctx
        return tree
    
    def is_empty(self) -> bool:
        return len(self.names) == 0


@dataclass 
class ReversibleAstInstruction(ReversibleAstExpr):
    """
    Представление одной строчки кода такого вида:

    output = function[input]
    """
    input: ReversibleAstArguments
    output: ReversibleAstArguments
    function: ast.AST
    names: set[str]
    is_plain: bool

    def _to_ast(self, assert_none=True) -> ast.expr:
        """
        Возвращает ast-представление прямой строки кода.
        """
        if self.is_plain:
            return self.function
        
        value = ast.Subscript(
            value=self.function,
            slice=self.input.to_ast(ctx=ast.Load()),
            ctx=ast.Load(),
        )

        if self.output.is_empty():
            # return ast.Expr(value=value)
            if assert_none:
                return ast_reversibility_assert(ast_is_none(value))
            else:
                return value
        
        return ast.Assign(
            targets=[self.output.to_ast(ctx=ast.Store())],
            value=value
        )
    
    @property
    def rev(self) -> ReversibleAstInstruction:
        """
        Возвращает обратную строку кода.
        """
        if not self.is_plain:
            function = ast.Attribute(value=self.function, attr='rev', ctx=ast.Load())
        else:
            function = self.function
        return ReversibleAstInstruction(self.output, self.input, function, self.names, self.is_plain)
    
    @staticmethod
    def from_ast(tree: ast) -> ReversibleAstInstruction:
        """
        Парсит обычный ast в своё внутреннее представление.
        """
        if (isinstance(tree, ast.Expr) and not isinstance(tree.value, ast.Subscript)) or isinstance(tree, ast.Assert) or isinstance(tree, ast.Raise) or isinstance(tree, ast.Pass):
            none_args = ReversibleAstArguments.from_ast(None)
            return ReversibleAstInstruction(none_args, none_args, tree, parse_ast_names(tree), is_plain=True)

        elif isinstance(tree, ast.Expr) and isinstance(tree.value, ast.Subscript):
            none_args = ReversibleAstArguments.from_ast(None)
            input = ReversibleAstArguments.from_ast(tree.value.slice)
            return ReversibleAstInstruction(input, none_args, tree.value.value, parse_ast_names(tree.value.value), is_plain=False)

        elif isinstance(tree, ast.Assign):
            if not isinstance(tree.value, ast.Subscript):
                raise RevpyCompilationError(f"Assigning in this line, so it is reversible function call. But then there must be '[destoyed_variable]' in the end!\n-->\t{ast.unparse(tree)}")
            input = ReversibleAstArguments.from_ast(tree.value.slice)
            output = ReversibleAstArguments.from_ast(tree.targets[0])
            return ReversibleAstInstruction(input, output, tree.value.value, parse_ast_names(tree.value.value), is_plain=False)
        else:
            assert False, f"ReversibleAstInstruction: bad AST object: '{tree}'"


    @property
    def signature(self) -> Signature:
        """
        Возвращает сигнатуру этой строки кода.
        """
        return Signature.from_line(self.input.names, self.output.names, self.names, ast.unparse(self.to_ast(assert_none=False)))


def get_expr_signature(expr: ast.AST, template: str = "{}") -> Signature:
    return Signature.from_line([], [], parse_ast_names(expr), template.format(ast.unparse(expr)))


@dataclass
class ReversibleAstIf(ReversibleAstExpr):
    if_test: ast.AST 
    fi_test: ast.AST
    body: ReversibleAstBlock
    orelse: ReversibleAstBlock
    _signature: Signature

    @staticmethod
    def from_ast(if_ast: ast.If, fi_test: ast.AST | None = None) -> ReversibleAstIf:
        assert isinstance(if_ast, ast.If)

        if_test = if_ast.test
        if fi_test is None:
            fi_test = if_test
        
        body = ReversibleAstBlock.from_ast(if_ast.body)
        orelse = ReversibleAstBlock.from_ast(if_ast.orelse)

        if_signature = get_expr_signature(if_test, "if {}:")
        fi_signature = get_expr_signature(if_test, "fi({})")

        signature = if_signature + (body.signature | orelse.signature) + fi_signature

        return ReversibleAstIf(if_test, fi_test, body, orelse, signature)
    
    @property
    def rev(self):
        return ReversibleAstIf(self.fi_test, self.if_test, self.body.rev, self.orelse.rev, self._signature.rev)

    def _to_ast(self):
        # body = 
        return ast.If(
            test=self.if_test,
            body=self.body.to_ast() + [ast_reversibility_assert(self.fi_test)],
            orelse=self.orelse.to_ast() + [ast_reversibility_assert(ast_not(self.fi_test))],
        )
    


@dataclass 
class ReversibleAstWhile(ReversibleAstExpr):
    while_test: ast.AST
    elihw_test: ast.AST
    body: ReversibleAstBlock
    _signature: Signature

    @staticmethod
    def from_ast(while_ast: ast.AST, elihw_test: ast.AST) -> ReversibleAstWhile:
        assert isinstance(while_ast, ast.While)

        if len(while_ast.orelse) != 0:
            raise RevpyCompilationError("'while' cycle must not have 'else' in reversible python!")

        body = ReversibleAstBlock.from_ast(while_ast.body)
        while_signature = get_expr_signature(while_ast.test, "while {}:")
        elihw_signature = get_expr_signature(elihw_test, "elihw({})")
        signature = while_signature + body.signature + elihw_signature

        for v in signature.dct.values():
            v.check()  # проверяем, что переменная имеет одинаковый статус существования по обеим сторонам блока

        return ReversibleAstWhile(while_ast.test, elihw_test, body, signature)
    
    def to_ast(self) -> list[ast.AST]:
        return [
            ast_reversibility_assert(ast_not(self.elihw_test)),
            ast.While(
                test=self.while_test, 
                body=self.body.to_ast() + [ast_reversibility_assert(self.elihw_test)],
                orelse=[],
            )
        ]
    
    @property
    def rev(self):
        return ReversibleAstWhile(self.elihw_test, self.while_test, self.body.rev, self._signature.rev)


def parse_condition(fi_expr: ast.AST, name: str) -> ast.AST | None:
    if not isinstance(fi_expr, ast.Expr):
        return None
    fi_call = fi_expr.value 
    if not isinstance(fi_call, ast.Call):
        return None
    if not isinstance(fi_call.func, ast.Name):
        return None
    if not fi_call.func.id == name:
        return None
    if not len(fi_call.args) == 1:
        raise RevpyCompilationError(f"fi must have only one argument (condition to check), but got:\n\t-->{ast.unparse(fi_expr)}")
    return fi_call.args[0]

@dataclass
class ReversibleAstBlock(ReversibleAstExpr):

    body: list[ReversibleAstExpr]
    s: Signature

    @staticmethod
    def from_ast(body: list[ast.AST]) -> ReversibleAstBlock:
        _body = []
        _signature = Signature({})
        idx = 0
        while idx < len(body):
            tree = body[idx]
            if isinstance(tree, ast.Expr) or isinstance(tree, ast.Assign) or isinstance(tree, ast.Assert) or isinstance(tree, ast.Raise) or isinstance(tree, ast.Pass):
                expr: ReversibleAstExpr = ReversibleAstInstruction.from_ast(tree)

            elif isinstance(tree, ast.If):
                fi_test = None
                if idx + 1 < len(body):
                    fi_test = parse_condition(body[idx+1], "fi")
                    if fi_test is not None:
                        idx += 1
                expr = ReversibleAstIf.from_ast(if_ast=tree, fi_test=fi_test)
            
            elif isinstance(tree, ast.While):

                elihw_test = None
                if idx + 1 < len(body):
                    elihw_test = parse_condition(body[idx+1], "elihw")
                    if elihw_test is not None:
                        idx += 1
                if elihw_test is None:
                    raise RevpyCompilationError(f"Every while must have elihw immidiately after body of the cycle!")
                
                expr = ReversibleAstWhile.from_ast(while_ast=tree, elihw_test=elihw_test)
            else:
                raise RevpyCompilationError(f"Construction {tree} is not allowed in RevPy")
            
            _body.append(expr)
            _signature = _signature + expr.signature

            idx += 1

        return ReversibleAstBlock(body=_body, s=_signature)
    
    @property
    def rev(self):
        body = list(reversed([expr.rev for expr in self.body]))   # обратные инструкции в обратном порядке
        return ReversibleAstBlock(body=body, s=self.s.rev)
    
    @property
    def signature(self):
        return self.s
    
    def to_ast(self) -> list[ast.AST]:
        res = []
        for expr in self.body:
            a = expr.to_ast()
            if isinstance(a, list):
                res.extend(a)
            else:
                res.append(a)
        return res
    

@dataclass
class ReversibleAstFunctionDef(ReversibleAstExpr):

    name: str
    args: ast.arguments
    body: ReversibleAstBlock
    
    input_name: str 
    output_name: str

    _signature: Signature
    
    def _to_ast(self) -> ast.expr:
        args = deepcopy(self.args)
        args.args.insert(0, ast.arg(arg=self.input_name))

        body: list = self.body.to_ast()
        return_expr = ast.Return(value=ast.Name(id=self.output_name, ctx=ast.Load()))
        body.append(return_expr)

        return ast.FunctionDef(
            name=self.name,
            args=args,  
            body=body,
            decorator_list=[]
        )
    
    @property
    def rev(self) -> ReversibleAstFunctionDef:
        return ReversibleAstFunctionDef(f'{self.name}_rev', self.args, self.body.rev, self.output_name, self.input_name, self._signature.rev)
    
    @staticmethod
    def from_ast(function_def: ast.expr) -> ReversibleAstFunctionDef:
        assert isinstance(function_def, ast.FunctionDef)

        # первый аргумент - всегда имя входной переменной
        args = deepcopy(function_def.args)
        input_name = args.args[0].arg
        assert isinstance(input_name, str)
        if len(args.args) < 1:
            raise RevpyCompilationError(f"Reversible function must have at least one argument, got zero.")
        del args.args[0]  # удаляем этот первый аргумент

        # последняя строчка - обязательно return <имя одной переменной>
        if function_def.body == 0:
            raise RevpyCompilationError(f"Reversible function must contain at least one line 'return <variable_name>', but got empty function")

        return_expr = function_def.body[-1]
        if not isinstance(return_expr, ast.Return):
            raise RevpyCompilationError(f"Last line of reversible function must be 'return <variable_name>', but got:\n\t--> {ast.unparse(return_expr)}")
        
        if not isinstance(return_expr.value, ast.Name):
            raise RevpyCompilationError(f"Last line of reversible function must be 'return <name of one variable>', but got:\n\t--> {ast.unparse(return_expr)}")
        
        output_name = return_expr.value.id
        assert isinstance(output_name, str)

        # всё остальное - тело
        body: ReversibleAstBlock = ReversibleAstBlock.from_ast(function_def.body[:-1])   # тут всё самое содержательное

        argument_names = set([arg.arg for arg in args.args])
        for name in argument_names:
            assert isinstance(name, str)

        input_signature = Signature.from_line(input=[], output=[input_name], capture=argument_names, line='function definition')
        output_signature = Signature.from_line(input=[output_name], output=[], capture=[], line=ast.unparse(return_expr))

        signature: Signature = input_signature + body.signature + output_signature

        if not argument_names.issubset(signature.names_capture):
            raise RevpyCompilationError(f"Names '{argument_names - signature.names_capture}' are parameters of reversible function (because they are not-first arguments), but are destroyed or created inside the function.")

        if not len(signature.names_input) == 0:
            raise RevpyCompilationError(f"Some variables are used before their creation: {signature.names_input}")

        if not len(signature.names_output) == 0:
            raise RevpyCompilationError(f"Some variables are not destroyed: {signature.names_output}.\nAll these variables must be explicitly destroyed!")
        
        return ReversibleAstFunctionDef(function_def.name, args, body, input_name, output_name, signature)
    
    @property
    def signature(self) -> Signature:
        return self._signature



########################################
###   COMPILATION OF GENERATED AST   ###
########################################


def _find_code(code: types.CodeType, name: str) -> types.CodeType | None:
    for const in code.co_consts:
        if isinstance(const, types.CodeType) and const.co_name == name:
            return const
    return None


def compile_function(
    function_def: ast.FunctionDef,
    globals: dict[str, Any],
    nonlocals: dict[str, types.CellType],
) -> types.FunctionType:
    factory_name = f"__factory_{function_def.name}"
    factory_def = ast.FunctionDef(
        name=factory_name,
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg=n) for n in nonlocals.keys()],
            kwonlyargs=[], kw_defaults=[], defaults=[],
        ),
        body=[
            function_def,
            ast.Return(value=ast.Name(id=function_def.name, ctx=ast.Load())),
        ],
        decorator_list=[],
    )
    module = ast.Module(body=[factory_def], type_ignores=[])
    ast.fix_missing_locations(module)

    # 1) Компилируем под тем же именем файла, что и оригинал — тогда
    #    co_filename и co_firstlineno указывают на реальные строки,
    #    и inspect.getsource / трейсбеки работают.
    filename = globals.get("__file__", "<generated>")
    module_code = compile(module, filename, "exec")

    factory_code = _find_code(module_code, factory_name)
    func_code = _find_code(factory_code, function_def.name)

    # 2) Правим qualname, чтобы трейсбек показывал имя функции,
    #    а не "__factory_f.<locals>.f".
    if sys.version_info >= (3, 11) and func_code.co_qualname != function_def.name:
        func_code = func_code.replace(co_qualname=function_def.name)

    closure = tuple(nonlocals[name] for name in func_code.co_freevars) or None

    # 3) Окружение для вычисления дефолтов: globals + значения из ячеек.
    env: dict[str, Any] = dict(globals)
    for name, cell in nonlocals.items():
        try:
            env[name] = cell.cell_contents
        except ValueError:
            pass  # пустая ячейка — дефолт, ссылающийся на неё, упадёт при eval

    defaults: tuple[Any, ...] | None = None
    if function_def.args.defaults:
        defaults = tuple(
            eval(compile(ast.Expression(d), filename, "eval"), env)
            for d in function_def.args.defaults
        )

    func = types.FunctionType(
        func_code,
        globals,
        function_def.name,
        defaults,
        closure,
    )

    # 4) Keyword-only дефолты.
    kw_defaults = function_def.args.kw_defaults
    if kw_defaults and any(d is not None for d in kw_defaults):
        func.__kwdefaults__ = {
            arg.arg: eval(compile(ast.Expression(d), filename, "eval"), env)
            for arg, d in zip(function_def.args.kwonlyargs, kw_defaults)
            if d is not None
        }

    return func


###########################
###   FINAL DECORATOR   ###
###########################

def get_nonlocals(function) -> dict[str, types.CellType]:
    orig_freevars = function.__code__.co_freevars
    orig_cells = dict(zip(orig_freevars, function.__closure__ or ()))
    return orig_cells

def get_function_def(function):
    source = inspect.getsource(function)
    tree = ast.parse(source)  # возвращает Module
    return tree.body[0]


def reversible(function: types.FunctionType) -> ReversibleFunction:
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

    if not revpy_assert_name is globals:
        nonlocals = nonlocals | {
            revpy_assert_name: types.CellType(reversibility_assert)
        }

    try:
        rf_def = ReversibleAstFunctionDef.from_ast(f_def)
    except RevpyCompilationError as e:
        raise RevpyCompilationError(e.msg) from None

    f_def = rf_def.to_ast()
    f = compile_function(f_def, globals, nonlocals)
    f.src = ast.unparse(f_def)

    f_rev_def = rf_def.rev.to_ast()
    f_rev = compile_function(f_rev_def, globals, nonlocals)
    f_rev.src = ast.unparse(f_rev_def)

    return ReversibleFunction(f=f, f_rev=f_rev)