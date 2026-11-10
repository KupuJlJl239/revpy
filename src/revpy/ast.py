from __future__ import annotations
import ast
from dataclasses import dataclass
from copy import deepcopy


from .base import RevpyCompilationError, reversibility_assert
from .lifetimes import Signature



#####################################
###   AST PARSING AND REVERTING   ###
#####################################


REVPY_ASSERT_NAME = reversibility_assert.__name__


class ReversibleAst:
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
    def rev(self) -> ReversibleAst:
        """
        Возвращает обратный кусок кода.
        """
        raise NotImplementedError()
    
    @staticmethod
    def from_ast(tree: ast.AST) -> ReversibleAst:
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
            func=ast.Name(id=REVPY_ASSERT_NAME, ctx=ast.Load()),
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



    
def parse_ast_args(args, allow_repeated=False) -> set[str]:
    if isinstance(args, ast.Name):
        assert isinstance(args.id, str)
        return set([args.id])
    elif isinstance(args, ast.Tuple) or isinstance(args, ast.List):
        res = set()
        for it in args.elts:
            A = parse_ast_args(it)
            if not allow_repeated and not res.isdisjoint(A):
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
class ReversibleAstInstruction(ReversibleAst):
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
class ReversibleAstIf(ReversibleAst):
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
class ReversibleAstWhile(ReversibleAst):
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


@dataclass 
class ReversibleAstFor(ReversibleAst):
    target: ast.AST
    iter: ast.AST
    body: ReversibleAstBlock
    _signature: Signature

    @staticmethod
    def from_ast(for_ast: ast.AST) -> ReversibleAstWhile:
        assert isinstance(for_ast, ast.For)

        if len(for_ast.orelse) != 0:
            raise RevpyCompilationError("'for' cycle must not have 'else' in reversible python!")

        vars = parse_ast_names(for_ast.target) | parse_ast_names(for_ast.iter)

        for_signature = Signature.from_line(input=[], output=[], capture=vars, line=f'for {ast.unparse(for_ast.target)} in {ast.unparse(for_ast.iter)}:')
        

        body = ReversibleAstBlock.from_ast(for_ast.body)
        signature = for_signature + body.signature

        for v in signature.dct.values():
            v.check()  # проверяем, что переменная имеет одинаковый статус существования по обеим сторонам блока

        if not vars.issubset(signature.names_capture):
            raise RevpyCompilationError(f"variables {vars - signature.names_capture} are iterated in for loop, but they are destroyed or created inside the body of the loop (which is prohibited!)")

        return ReversibleAstFor(for_ast.target, for_ast.iter, body, signature)
    
    def to_ast(self) -> list[ast.AST]:
        return [
            ast.For(
                target=self.target, 
                iter=self.iter,
                body=self.body.to_ast(),
                orelse=[],
            )
        ]
    
    @property
    def rev(self):
        if isinstance(self.iter, ast.Call) and isinstance(self.iter.func, ast.Name) and self.iter.func.id == 'reversed':
            if not (len(self.iter.args) == 1 and len(self.iter.keywords) == 0):
                raise RevpyCompilationError(f"'reversed' must have 1 positional argument (got {len(self.iter.args)}) and 0 keyword arguments (got {len(self.iter.keywords)})")
            iter = self.iter.args[0]
        else:
            iter = ast.Call(
                func=ast.Name(id='reversed', ctx=ast.Load()),
                args=[self.iter],
                keywords=[],
            )
        return ReversibleAstFor(self.target, iter, self.body.rev, self._signature.rev)


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
class ReversibleAstBlock(ReversibleAst):

    body: list[ReversibleAst]
    s: Signature

    @staticmethod
    def from_ast(body: list[ast.AST]) -> ReversibleAstBlock:
        _body = []
        _signature = Signature({})
        idx = 0
        while idx < len(body):
            tree = body[idx]
            if isinstance(tree, ast.Expr) or isinstance(tree, ast.Assign) or isinstance(tree, ast.Assert) or isinstance(tree, ast.Raise) or isinstance(tree, ast.Pass):
                expr: ReversibleAst = ReversibleAstInstruction.from_ast(tree)

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

            elif isinstance(tree, ast.For):
                expr: ReversibleAst = ReversibleAstFor.from_ast(tree)

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
class ReversibleAstFunctionDef(ReversibleAst):

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