# RevPy

**English** | [Русский](https://github.com/KupuJlJl239/revpy/blob/main/docs/README.ru.md)

**A reversible programming language embedded in Python.**

The `RevPy` library allows you to write Python functions that can be executed in two directions: **forward** and **backward**. You write an ordinary Python function (but following certain rules), and the `@reversible` decorator compiles it into a pair of forward and reverse functions. Thus, the reverse function does not need to be written by hand — it is generated automatically.

```python
from revpy import reversible, ReversibleFunction

add = ReversibleFunction(lambda x, a: x + a, lambda x, a: x - a)

@reversible
def twice(x):
    y = add(1)[x]
    z = add(1)[y]
    return z

twice[0]      # -> 2 = twice(0)
twice.rev[2]  # -> 0 — the result of the automatically generated code
```

`RevPy` is inspired by reversible programming languages
(such as [**Janus**](https://en.wikipedia.org/wiki/Janus_(reversible_computing_programming_language))),
but remains a tool inside Python, relying entirely on its syntax.

Features of `RevPy`:
- **Expressiveness**: there are reversible versions of `if` and `while` (the constructs `if/fi` and `while/elihw` respectively). Thanks to this, arbitrary reversible algorithms can be implemented with `RevPy`.
- **Reliability**: variable lifetimes are checked statically — every variable must be destroyed exactly once, and its liveness must be the same in all branches and iterations (similar to the ownership logic in `Rust`); this lets you catch most errors before running the code.
- **Transparency**: you can obtain the explicit `python` code generated automatically by the `@reversible` decorator, copy this code, read it, and run it separately from `RevPy`.
- **Flexibility**: easily integrates with any libraries for `Python`, including `numpy` and `pytorch`, as well as with any kind of reversibility (partial or full, bit-exact or up to computation error).
- **Speed**: almost the same as ordinary `Python`, all thanks to direct compilation instead of step-by-step interpretation. Slightly lower because of the embedded runtime reversibility checks for the `if/fi` and `while/elihw` conditions.
- **Minimalism**: just two objects from `RevPy` are more than enough:
    - `ReversibleFunction` — for artificially creating a reversible function from a pair of forward and reverse functions defined beforehand
    - `@reversible` — for compiling a reversible program
- **Freedom from dependencies**: requires **only Python 3.9+**, and no other dependencies.

The purpose of `RevPy`:
- to simplify the development of reversible algorithms, for example such as:
    - compression algorithms
    - reversible neural networks
- to bring the whole richness of the Python infrastructure to reversible programming

## Installation

```bash
pip install revpy-lang
```

## Contents

- [Key concepts](#base)
- [`ReversibleFunction`: basic reversible functions](#base_functions)
- [`@reversible`: reversible programming](#complex_functions)
    - [`if/fi`](#if)
    - [`while/elihw`](#while)
- [API](#api)
- [more examples](https://github.com/KupuJlJl239/revpy/tree/main/examples)

<p id="base">  </p>

# Key concepts

This section describes the basic principles of working with `RevPy`. Read this section before using the library — it introduces the terms on which everything else relies.

<p id="rinfo"></p>

**Significant information** — the information that must not be lost during the execution of the program.
- What counts as "significant" and what doesn't — **you decide**.
- What counts as "preserving information" — **you also decide**. For example:
    - *hardware preservation of information* — the original information can be restored bit-exactly
    - *mathematical preservation of information* — the original information can be restored up to float computation error
    - *preservation of information only under certain conditions* — "reversibility holds, as long as event X doesn't happen", where X is, for example, multiplication or division by 0 somewhere in the program

<p id="rstate"></p>

**Significant program state** — the part of the entire program state (part of the variables, fields, etc.) consisting of all the [_significant information_](#rinfo).

<p id="rfunc"></p>

**Reversible function** — a function in `python` for which there exists an inverse one, i.e. one that restores all the original [_significant state_](#rstate) from the final _significant state_.

<p id="brfunc"></p>

**Basic reversible function** — a [_reversible function_](#rfunc) that you have defined explicitly as a pair of _forward_ and _reverse_ functions. You can do this, for example, like this: `ReversibleFunction(f, f_rev)`.

> You must write the basic _forward_ and _reverse_ functions by hand. The responsibility for correctness (i.e. that these functions are inverse to each other in the sense you defined) lies entirely and completely with you.

> `RevPy` has no built-in _basic reversible functions_. Therefore you **are obliged** to provide them yourself.

<p id="crfunc"></p>

**Complex reversible function** — a function automatically generated by the `@reversible` decorator from other [_reversible functions_](#rfunc) (both _basic_ and _complex_).

> `@reversible` guarantees that if all the _reversible functions_ used in it are correct, then the resulting function is also correct.

<p id="rapi"></p>

## `RevPy-API`: the interface standard for reversible functions

```python
output = f[input]
input = f.rev[output]
```

- `[]` — the reversible function call operator (defined via `.__getitem__`)
- `.rev` — the function inversion operator

Thus, _duck typing_ is used: any object that has these methods can be considered a reversible function.

<p id="revpyfunc"></p>

**`RevPy`-function** — any reversible function satisfying the `RevPy-API`.

Semantics:
- a call to `f` destroys the `input` and creates the `output`
- along the way, a call to `f` may modify other variables whose references are captured inside `f`
- a call to `f.rev` rolls back all changes:
    - destroys the `output` and creates the `input`
    - returns the [_significant state_](#rstate) of all captured variables to their original _significant state_
- `input` and `output` — any `python` objects (in particular, this may be a `tuple` if by meaning you need to accept or return several objects)
- in total: any reversible function destroys exactly one object and creates exactly one object
- a function may be **partially reversible**:
    - either both `f` and `f.rev` work correctly, undoing each other's effect
    - or both throw an exception during execution / loop forever
    - i.e. it must not be the case that a call to `f` succeeded and returned something, while the reverse call `f.rev` did not restore the state (failed with an error, or returned the wrong thing, or did not terminate at all)
- a function may be **reversible only under certain conditions**:
    - if these conditions on the input or intermediate values are met — reversibility holds
    - otherwise — anything goes

<p id="base_functions"></p>

# `ReversibleFunction`: basic reversible functions

— builds a [_`RevPy`-function_](#revpyfunc) from a pair of ordinary functions (forward and reverse).

```python
rf = ReversibleFunction(f, f_rev)

rf[x]           # returns f(x)
rf.rev[x]       # returns f_rev(x)
rf.rev.rev[x]   # returns f(x)

rf(a, b=1)[x]       # returns f(x, a, b=1)
rf(a, b=1).rev[x]   # returns f_rev(x, a, b=1)
rf.rev(a, b=1)[x]   # returns f_rev(x, a, b=1)
rf.rev(a, b=1).rev[x]   # returns f(x, a, b=1)
```

- the first argument is considered the `input`
- the remaining arguments are considered _captured_ external values
- accordingly, all arguments of `f` and `f_rev` except the first must have the same names and the same default values
- `*args` and `**kwargs` are allowed in the definitions of `f` and `f_rev`

## The set of basic functions for the following parts of the README

```python
from revpy import ReversibleFunction, reversibility_assert
import numpy as np

move = ReversibleFunction(
    f=lambda x: x,
    f_rev=lambda x: x,
)

add = ReversibleFunction(
    f=lambda x, a: x + a, 
    f_rev=lambda x, a: x - a
)

mult = ReversibleFunction(
    f=lambda x, a: x * a, 
    f_rev=lambda x, a: x / a
)


def init(none, value):
    reversibility_assert(none is None)
    return value

def destroy(x, value):
    reversibility_assert(x == value)
    return None

init = ReversibleFunction(init, destroy)
destroy = init.rev


def init_float(none, value, **kwargs):
    reversibility_assert(none is None)
    return value

def destroy_float(x, value, **kwargs):
    reversibility_assert(np.isclose(x, value, **kwargs).all())
    return None

init_float = ReversibleFunction(init_float, destroy_float)
destroy_float = init_float.rev
```

<p id="base_rfunc">  </p>

We have defined 5 [basic reversible functions](#brfunc):
- `move` — a function that does nothing
    - thus, `output = move[input]` takes ownership from the input and transfers it to the output
    - the name is borrowed from move semantics in `C++`
    - we will use this function for packing/unpacking:
        - `x, y = move[x_and_y]`
        - `x_and_y = move[xy]`
- `add(a)` — adding the constant `a` to the input
- `mult(a)` — multiplying the input by the constant `a`
- `init(value)` — initializing an object with the constant value `value`
    - `destroy(value)` — the inverse of it, destroying an object with the assertion that the input equals the constant value `value`
    - we will use it for any Python objects that make sense to compare via `==`
- `init_float(value)` — initializing a float with the constant value `value`
    - `destroy_float(value)` — the inverse of it, destroying a float with the assertion that it equals the constant value `value` **up to computation error** (this is the only difference from the ordinary `init/destroy`)
    - we will use it for float numbers and numpy arrays of any shapes

In what sense will we understand reversibility from now on?
- for arbitrary Python objects — up to `==`
- for float numbers and numpy arrays — up to computation error
- reversibility is **partial**:
    - either reversibility holds, or an error at runtime
- reversibility **only under certain conditions**:
    - if there was no multiplication or division by 0 — reversibility holds
    - otherwise — not necessarily

> For runtime reversibility checks we used [`reversibility_assert`](#reversibility_assert). This is exactly the function that `@reversible` inserts into the automatically generated code for [`if/fi`](#if) and [`while/elihw`](#while). This function simply throws a [`ReversibilityError`](#ReversibilityError) exception if the condition turns out to be false. Instead of it we could have used an ordinary `assert`. We use `reversibility_assert` solely for the purpose of emphasizing that the check concerns reversibility, and not something else.

<p id="complex_functions"></p>

# `@reversible`: reversible programming

— generates a _`RevPy`-function_ by analyzing the code of a `python` function.

Does 2 things:
1. Generates the code of the reverse function, placing reverse instructions in reverse order.
2. Performs reversibility checks:
    - at compile time: checks the lifetimes of all variables
    - at runtime: inserts into the source code the [`reversibility_assert`](#reversibility_assert) checks

You can obtain the automatically generated code via `.src` (see examples in the examples for [`if/fi`](#if_ex) and [`while/elihw`](#while_ex)).

## Syntax

The following constructs are allowed, described below:
- reversible line of code
- `return`
- `if/fi` (and `elif`)
- `while/elihw`
- `for`
- arbitrary line of code (in particular `raise` and `assert`)

`if`, `while` and `for` may be nested inside each other any number of times and in any way.
In particular, the following are allowed:
- nested loops
- `if` inside a loop
- a loop inside `if`
- etc.

Not allowed (will cause a compilation error):
- `break` and `continue`, `try/except`, `yield`, `while ... else`, `for ... else`
  - all of them introduce tricky control flow, which makes it unclear how to execute the code in the reverse direction ("undo" their action)
- `class` and `def`
  - it is unclear how to naturally reverse the operation of declaring a class / function
- `with` _(may be added in the future)_
- `global` and `nonlocal` _(may be added in the future)_
- `match/case` _(may be added in the future)_

Recursion is allowed.

### Reversible line of code

```python
created_variables = expression[destroyed_variables]
```
- `expression` — any expression whose result is a _`RevPy`-function_
- `created_variables` and `destroyed_variables` — any lists or tuples of _local variable names_

`@reversible` transforms such a line into a paired one that undoes the action of the original:
```python
destroyed_variables = expression.rev[created_variables]
```

Here are all the rules checked at compile time concerning a single line of code:
- `created_variables` must not overlap with the names appearing in `expression`
- `destroyed_variables` must not overlap with the names appearing in `expression`

You can think of it like this:
- destruction works first
- then variables are captured for `expression`
    - if some of them were destroyed, they can no longer be captured
- at the end new variables are created

Examples:
```python
y = f[x]                    # OK  -->  x = f.rev[y]
x = f[x]                    # OK  -->  x = f.rev[x]
x, (b, c) = f[x, (a, b)]    # OK  -->  x, (a, b) = f.rev[x, (b, c)]
y = f(a, b=b, c=3)[x]       # OK  -->  x = f(a, b=b, c=3).rev[y]


y = f[array[0]] # compilation error: array[0] is an expression, not a local variable name
point.x = f[x]  # compilation error: point.x is an expression, not a local variable name
```

```python
y, z = (f + g)[x]   # OK  -->  x = (f + g).rev[y, z]  
```
- OK if the result of `f + g` is a reversible function
- `ReversibleFunction` does not have a `+` operator, so in this example `f` and `g` must be some objects not related to `RevPy` for which `+` returns a [`RevPy`-function](#revpyfunc) (i.e. an object with `[]` and `.rev` operators)
- RevPy doesn't think about this and simply transforms the syntactic expressions

#### Empty input/output of a reversible function

It is also allowed to omit `created_variables` and/or `destroyed_variables`:

```python
expression[destroyed_variables]
destroyed_variables = expression.rev[None]  # paired line to the previous one

created_variables = expression[None]
expression.rev[created_variables]   # paired line to the previous one
```

The absence of `created_variables` is equivalent to the assertion that the expression must return `None`:
```python
expression[destroyed_variables]  # the original line
reversibility_assert(expression[destroyed_variables] is None)  # after @reversible
```

### `return`

The last line of code must look like:
```
return <local variable name>
```

`return` is not allowed in other places of the function. It is also not allowed inside any constructs — inside `if/fi`, `while` and `for`.
Thus, `return` must occur exactly once — in the last line.

The reason for all these restrictions is simple — we need to know how to execute the function in the reverse direction. If `return` appears somewhere in a non-trivial place, how would we know where to start executing the reverse function, i.e. where the entry point is?

```python
return x    # OK

return x, y     # compilation error: x, y is a tuple, not a local variable name
return array[0] # compilation error: array[0] is an expression, not a local variable name
```

If you need to return a pair of variables, simply pack them into a tuple (for example, using [`move`](#base_rfunc)):

```python
res = move[x, y]    # OK
return res          # OK
```

<p id="if"></p>

### `if/fi`

In reversible programming we must be able to execute a program in both directions — forward and backward.

How to execute `if` on the forward pass is clear: check the condition, and depending on it choose whether to go into the `if` branch or the `else` branch.

But how to execute `if` on the backward pass? — for this, immediately after exiting it, we must know exactly which branch we came from (and on the backward pass we will go into that branch). For this, the construct `fi(C)` is used, where the condition `C` must be true when exiting the `if` branch and false when exiting the `else` branch. On the forward pass this is checked by inserting `reversibility_assert(C)` at the end of the branches. On the backward pass `if` and `fi` swap roles: we choose the branch by the condition from `fi`, and use the condition from `if` to check when exiting the branch.

Using `elif` is allowed, but then you won't be able to specify the closing `fi`, and the reverse condition will be taken by default the same as it was in `if`.

The original construct:
```python
if condition:
    <if_body>
else:  # optional (empty <else_body> by default)
    <else_body>
fi(reverse_condition) # optional (reverse_condition=condition by default)
```

Here is what is produced in the forward function after `@reversible`:
```python
if condition:
    <if_body>
    reversibility_assert(reverse_condition)
else:
    <else_body>
    reversibility_assert(not reverse_condition)
```

Here is what is produced in the reverse function after `@reversible`:
```python
if reverse_condition:
    <reversed if_body>
    reversibility_assert(condition)
else:
    <reversed else_body>
    reversibility_assert(not condition)
```

<p id="if_ex"></p>

#### Example

(basic functions defined [above](#base_rfunc))

```python
# if condition is true, returns a * x + b
# otherwise returns x + 1

@reversible
def f(x, a, b, condition: bool):
    
    if condition:
        x = mult(a)[x]
        x = add(b)[x]    
    else:
        x = add(1)[x]
    fi(condition)   # optional
    return x

f(a=2, b=3, condition=True)[1.0]     # -> 5.0 = f(1.0, 2, 3, True)
f(a=2, b=3, condition=True).rev[5.0] # -> 1.0, the result of the automatically generated code

f(a=2, b=3, condition=False)[1.0]     # -> 2.0 = f(1.0, 2, 3, False)
f(a=2, b=3, condition=False).rev[2.0] # -> 1.0, the result of the automatically generated code
```

Automatically generated code of the forward function:
```python
print(f.src)
```

```python
def f(x, a, b, condition: bool):
    if condition:
        x = mult(a)[x]
        x = add(b)[x]
        reversibility_assert(condition, "reversibility_assert is False: 'condition'")
    else:
        x = add(1)[x]
        reversibility_assert(not condition, "reversibility_assert is False: 'not condition'")
    return x
```

Automatically generated code of the reverse function:
```python
print(f.rev.src)
```

```python
def f_rev(x, a, b, condition: bool):
    if condition:
        x = add(b).rev[x]
        x = mult(a).rev[x]
        reversibility_assert(condition, "reversibility_assert is False: 'condition'")
    else:
        x = add(1).rev[x]
        reversibility_assert(not condition, "reversibility_assert is False: 'not condition'")
    return x
```

<p id="while"></p>

### `while/elihw`

With `while` in reversible programming the situation is completely analogous to the situation with `if`. On the backward pass we must know when to exit the loop, and whether we need to enter it at all. For this, the paired construct to `while` is used — `elihw`, which on the forward pass turns into condition checks, and on the backward pass — into `while`.

The original construct:
```python
while condition:
    <body>
elihw(reverse_condition)
```

`reverse_condition`:
- must be false immediately before the first entry into the loop
- must be true every time the end of the loop is reached

Unlike `fi`, for which by default `reverse_condition = condition`, for `elihw` such a condition is almost never suitable. Therefore `elihw` is **mandatory** — without it you will get a compilation error.

Here is what is produced in the forward function after `@reversible`:
```python
reversibility_assert(not reverse_condition)
while condition:
    <body>
    reversibility_assert(reverse_condition) 
```

Here is what is produced in the reverse function after `@reversible`:
```python
reversibility_assert(not condition)
while reverse_condition:
    <reversed body>
    reversibility_assert(condition) 
```

<p id="while_ex"></p>

#### Example

(basic functions defined [above](#base_rfunc))

```python
@reversible
def add_n_times(x, a, n=10):
    i = init(0)[None]
    while i < n:
        x = add(a)[x]
        i = add(1)[i]
    elihw(i > 0)
    destroy(n)[i]
    return x

add_n_times(a=1, n=10)[0]   # -> 10 = add_n_times(1, a=1, n=10)
add_n_times(a=1).rev[10]    # -> 0, the result of the automatically generated code
```

```python
print(add_n_times.src)
```

```python
def add_n_times(x, a, n=10):
    i = init(0)[None]
    reversibility_assert(not i > 0, "reversibility_assert is False: 'not i > 0'")
    while i < n:
        x = add(a)[x]
        i = add(1)[i]
        reversibility_assert(i > 0, "reversibility_assert is False: 'i > 0'")
    reversibility_assert(destroy(n)[i] is None, "reversibility_assert is False: 'destroy(n)[i] is None'")
    return x
```

```python
print(add_n_times.rev.src)
```

```python
def add_n_times_rev(x, a, n=10):
    i = destroy(n).rev[None]
    reversibility_assert(not i < n, "reversibility_assert is False: 'not i < n'")
    while i > 0:
        i = add(1).rev[i]
        x = add(a).rev[x]
        reversibility_assert(i < n, "reversibility_assert is False: 'i < n'")
    reversibility_assert(init(0).rev[i] is None, "reversibility_assert is False: 'init(0).rev[i] is None'")
    return x
```

<p id="for"></p>

### `for`

— iterates over the elements of some collection. On the backward pass the iteration goes in reverse order.

The original construct:
```python
for <variables> in <collection>:
    <body>
```

Here is what is produced in the reverse function after `@reversible`:
```python
for <variables> in reversed(<collection>):
    <reversed body>
```

You can think of it like this:
- `for` extracts references to some objects from the collection (captures them similarly to the parameters of a reversible function)
- accordingly, the loop body does not own these objects, and cannot create or destroy them (but can modify them inplace)
- if we traverse the collection backwards and perform the reverse actions in reverse order on each iteration, we will return the program state to its original state
- however, for this we also need to require that the collection itself does not change (elements are not added to it, their order is not changed, etc., but the contents of its elements may change)

Rules:
- `<collection>` — any expression whose result must be a collection supporting `reversed`; this collection must be the same at the beginning and at the end of the loop
    - the responsibility for all of this is on you!
    - `@reversible` merely rearranges the source code and checks variable lifetimes
    - for `reversed` to work, the collection needs to have a `__reversed__` method or `__len__`+`__getitem__`:
      - `list`, `tuple`, `range`, `dict` will work
      - `set` **will NOT work**
      - iterators, for example `enumerate` and `zip`, **will NOT work**
        - the exception is `reversed` itself — its presence is checked separately, and if it is present, it is removed
      - generators **will NOT work**

- `<variables>` — a variable name, a tuple/list of names, or nested tuples/lists of names. In short, everything as in an ordinary `for`.

> things like "this expression is a collection that supports `reversed`" or "this collection does not change inside the loop" cannot be checked statically within Python, and revpy deliberately does not deal with this

> `@reversible` does not add any runtime checks to `for` (unlike `if/fi` and `while/elihw`). All responsibility — for the immutability of the collection and the ability to apply `reversed` to it — is on you!

Lifetime rules:
- variables appearing in the expressions `<variables>` and `<collection>` cannot be created/destroyed inside the loop body (otherwise — compilation error)
- variables appearing in the expression `<variables>` must not exist before the loop, and will not exist after the loop body (otherwise — compilation error)

<p id="for_ex"></p>

#### Example

(basic functions defined [above](#base_rfunc))

```python
@reversible
def add_range(x, n=10):
    for i in range(n):
        x = add(i)[x]
    return x

add_range(n=10)[0]   # -> 45 = add_range(0, n=10) = 0 + 1 + 2 + ... + 9
add_range().rev[45]  # -> 0, the result of the automatically generated code
```

```python
print(add_range.src)
```

```python
def add_range(x, n=10):
    for i in range(n):
        x = add(i)[x]
    return x
```

```python
print(add_range.rev.src)
```

```python
def add_range_rev(x, n=10):
    for i in reversed(range(n)):
        x = add(i).rev[x]
    return x
```

### Other lines

Arbitrary lines of code are also allowed. `@reversible` leaves such lines untouched — they are executed as is on both the forward and the backward pass.

You bear full responsibility for ensuring that the execution of these lines of code does not change the [_significant state_](#rstate).

Here are the rules by which `@reversible` identifies these lines of code:
- the result must not be written to a variable (there must be no assignment)
- the last operation in the line must not be `[]`

Examples of such lines:
```python
print(x)
```

```python
assert x == 0
```

```python
raise Exception("some error!")
```

#### Example

```python
@reversible
def add_n_times(x, a, n=10):
    i = init(0)[None]
    while i < n:
        x = add(a)[x]
        i = add(1)[i]
        print(x, end=' ')  # executed both on the forward and on the backward pass
    elihw(i > 0)
    destroy(n)[i]
    return x

print(f"result={add_n_times(a=1)[0]}")      # forward call
print(f"result={add_n_times(a=1).rev[10]}") # backward call
```

Output:
```
1 2 3 4 5 6 7 8 9 10 result=10
10 9 8 7 6 5 4 3 2 1 result=0
```

## Reversibility check at compile-time

The main thing here is **static lifetime checking**. This is quite similar to how it works in `rust`. In a `@reversible` function the lifetime of every variable must be determined statically.

- the first argument is considered to be passed by value (the function takes ownership of it, assuming responsibility for its destruction)

- the remaining arguments are considered to be passed by reference (ownership remains with the calling function, and in the current function such variables cannot be created/destroyed)

- after destruction (passing to `[]`) the variable ceases to exist

- assignments of a value to existing variables are not allowed

- in all lines of code the existence / absence of a variable must be determined statically (i.e. not depend on which `if` branch we took, or how many times we executed the `while` loop)

- `return` destroys the last local variable, returning ownership of it out of the function
    - as a result, at the end all local variables must be destroyed

`@reversible` checks all these conditions **at the code analysis stage**. If something is violated — you will see a `RevpyCompilationError` exception.

```python
@reversible
def affine(
    # Input variable whose ownership the function takes.
    # Must be destroyed, otherwise — compilation error.
    x,     

    # Captured variables, cannot be created/destroyed.
    # Otherwise — compilation error.
    a, b    
):
    # the only local variable here is x
    # (since it is the first argument of the function)

    y = mult(a)[x]   
    # here the variable x no longer exists;
    # any use of it will cause a compilation error
    # the only local variable here is y

    z = add(b)[y]
    # here the variable y no longer exists;
    # any use of it will cause a compilation error
    # the only local variable here is z

    # z is the last remaining local variable, and that is what we return
    return z  

affine(a=2, b=3)[1.0]      # → 5.0   (forward call)
affine(a=2, b=3).rev[5.0]  # → 1.0   (backward call)
```

### Examples of typical lifetime errors

#### if

Here are typical examples of errors related to `if` branching:

```python
if C:
    y = f[x]  # in this branch the variable y is created, and x is destroyed
else: 
    pass      # in this branch the variable y is NOT created, and x is NOT destroyed
fi(C)
```

```python
if C:
    y = f[x]  # in this branch the variable y is created

# else is empty by default, and there y is NOT created, and x is NOT destroyed
```

Here are examples of correct code:

```python
# OK
if C:
    y = f[x]
else: 
    y = move[x]
```

```python
# OK
if C:
    x = f[x]
    y = g[x]
    z = h[y]
else: 
    z = move[x]
```

#### while

Here are typical examples of errors related to `while` loops:

```python
while condition:
    # with repeated execution of the loop, y will be created many times, which is forbidden
    # with repeated execution of the loop, x will be destroyed many times, which is forbidden
    y = f[x]    
elihw(reverse_condition)
```

Here are examples of correct code:

```python
# OK
while condition:
    x = f[x]
    y = g[x]  
    x = h[y] 
elihw(reverse_condition)
```

# API
<p id="api"> </p>

Here is the list of all objects you can import.

```python
# the most important decorator
from revpy import reversible

# for combining two inverse functions into one reversible one
from revpy import ReversibleFunction 

# reversibility_assert will be needed if you want to copy the code of a reversible function (`.src`) and run it separately
# or you can use it in basic reversible functions instead of assert (optional)
from revpy import reversibility_assert

# exception classes: needed only if you want to catch them
from revpy import ReversibilityError, RevpyCompilationError

# stubs for syntactic constructs: needed only so that the code analyzer in your IDE doesn't complain about the nonexistent `elihw` and `fi`, i.e. only for beauty
from revpy import elihw, fi
```

<p id="reversible"></p>

## `@reversible`

```python
def reversible(function: types.FunctionType) -> ReversibleFunction:
    """
    Compiles a function into a reversible function.

    - the first argument is considered the _input_
    - the remaining arguments are considered _parameters_ (i.e. captured values)
    - the last line must be 'return <variable name>', and this variable is considered the _output_
    
    :param function: a function written with the revpy rules
    :return reversible_function: an instance of the class ReversibleFunction
    """
    ...   # here main logic
    return reversible_function
```

- uses the same scopes that the original function had (i.e. the same `.__globals__` and `.__closure__`)

Runtime reversibility checks:
- by default uses [`reversibility_assert`](#reversibility_assert) for reversibility checks
- you can define your own function with the name `"reversibility_assert"`, and then `@reversible` will use your function instead of the built-in one!
  - `@reversible` looks at the variable named `"reversibility_assert"` in `.__globals__`, and if it finds one, uses it instead of the built-in function
  - the required signature: `reversibility_assert(condition: bool, message: str)`

Source code generation:
- `@reversible` registers the generated code in `linecache`

<p id="ReversibleFunction"></p>

## `ReversibleFunction`

```python
from inspect import getsource
from textwrap import dedent

class ReversibleFunction:
    """
    A wrapper class over a pair of functions f and f_rev, combining them into a single reversible function.

    The first argument of the functions is considered the value being destroyed, the rest — parameters (which are not destroyed).
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
```

<p id="reversibility_assert"></p>

## `reversibility_assert`

```python
def reversibility_assert(condition, message=''):
    if not condition:
        raise ReversibilityError(message)
```

## Exception classes

Use them to catch compilation and runtime errors.

<p id="ReversibilityError"></p>

### `ReversibilityError`

```python
class ReversibilityError(Exception):
    """
    Base class for reversibility errors at runtime.
    """
    pass
```

<p id="RevpyCompilationError"></p>

### `RevpyCompilationError`

```python
@dataclass
class RevpyCompilationError(Exception):
    """
    Base class for reversibility errors at the code analysis stage.
    """
    msg: str
```

## Stubs for syntactic constructs

<p id="fi"></p>

### `fi`

```python
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
```

<p id="elihw"></p>

### `elihw`

```python
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
```