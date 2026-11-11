"""
Tests for RevPy.

Structure:
    1. TestReversibleFunction   — basic ReversibleFunction behavior, no errors
    2. TestReversiblePrograms   — simple @reversible programs
    3. TestIfFi                 — if/fi
    4. TestWhileElihw           — while/elihw
    5. TestFor                  — for
    6. TestScopes               — closures
    7. TestArbitraryLines       — print / assert run on both passes
    8. TestCompilationErrors    — RevpyCompilationError cases
    9. TestRuntimeErrors        — ReversibilityError cases
"""
import pytest
import numpy as np

from revpy import (
    reversible,
    ReversibleFunction,
    reversibility_assert,
    ReversibilityError,
    RevpyCompilationError,
    fi,
    elihw,
)


# ============================================================
# Shared base functions (same as in README)
# ============================================================

move = ReversibleFunction(
    f=lambda x: x,
    f_rev=lambda x: x,
)

add = ReversibleFunction(
    f=lambda x, a: x + a,
    f_rev=lambda x, a: x - a,
)

mult = ReversibleFunction(
    f=lambda x, a: x * a,
    f_rev=lambda x, a: x / a,
)


def _init(none, value):
    reversibility_assert(none is None)
    return value


def _destroy(x, value):
    reversibility_assert(x == value)
    return None


init = ReversibleFunction(_init, _destroy)
destroy = init.rev


def _init_float(none, value, **kwargs):
    reversibility_assert(none is None)
    return value


def _destroy_float(x, value, **kwargs):
    reversibility_assert(np.isclose(x, value, **kwargs).all())
    return None


init_float = ReversibleFunction(_init_float, _destroy_float)
destroy_float = init_float.rev


# ============================================================
# 1. ReversibleFunction — basic behavior
# ============================================================


class TestReversibleFunction:
    def test_move_identity(self):
        assert move[42] == 42
        assert move.rev[42] == 42

    def test_move_tuple(self):
        assert move[1, 2] == (1, 2)
        assert move[(1, 2)] == (1, 2)
        x, y = move[1, 2]
        assert (x, y) == (1, 2)

    def test_add(self):
        assert add(2)[3] == 5
        assert add(2).rev[5] == 3
        assert add.rev(2)[5] == 3

    def test_mult(self):
        assert mult(2)[3] == 6
        assert mult(2).rev[6] == 3

    def test_rev_rev(self):
        assert add(2).rev.rev[3] == 5

    def test_call_returns_new_object(self):
        rf = add(2)
        assert rf is not add
        assert rf[3] == 5
        assert rf.rev[5] == 3

    def test_init_destroy(self):
        assert init(42)[None] == 42
        assert destroy(42)[42] is None

    def test_init_float_destroy_float(self):
        x = init_float(3.14)[None]
        assert abs(x - 3.14) < 1e-9
        assert destroy_float(3.14)[x] is None

    def test_init_float_numpy(self):
        x = init_float(np.array([1.0, 2.0]))[None]
        assert np.allclose(x, [1.0, 2.0])
        assert destroy_float(np.array([1.0, 2.0]))[x] is None


# ============================================================
# 2. @reversible — simple programs
# ============================================================


class TestReversiblePrograms:
    def test_twice(self):
        @reversible
        def twice(x):
            y = add(1)[x]
            z = add(1)[y]
            return z

        assert twice[0] == 2
        assert twice.rev[2] == 0

    def test_affine(self):
        @reversible
        def affine(x, a, b):
            y = mult(a)[x]
            z = add(b)[y]
            return z

        assert affine(a=2, b=3)[1.0] == 5.0
        assert affine(a=2, b=3).rev[5.0] == 1.0


# ============================================================
# 3. if/fi
# ============================================================


class TestIfFi:
    def test_if_true_branch(self):
        @reversible
        def f(x, c):
            if c:
                x = add(1)[x]
            else:
                x = add(2)[x]
            return x

        assert f(c=True)[10] == 11
        assert f(c=True).rev[11] == 10

    def test_if_false_branch(self):
        @reversible
        def f(x, c):
            if c:
                x = add(1)[x]
            else:
                x = add(2)[x]
            return x

        assert f(c=False)[10] == 12
        assert f(c=False).rev[12] == 10

    def test_if_no_else(self):
        @reversible
        def f(x, c):
            if c:
                x = add(5)[x]
            return x

        assert f(c=True)[10] == 15
        assert f(c=True).rev[15] == 10
        assert f(c=False)[10] == 10
        assert f(c=False).rev[10] == 10

    def test_if_default_fi_when_condition_is_stable(self):
        # condition x > 0 stays true/false in each branch, so default fi works
        @reversible
        def f(x):
            if x > 0:
                x = mult(2)[x]
            else:
                x = add(-1)[x]
            return x

        assert f[5] == 10
        assert f.rev[10] == 5
        assert f[0] == -1
        assert f.rev[-1] == 0

    def test_if_custom_fi(self):
        # reverse_condition = (x > 100) differs from condition = (x > 0)
        @reversible
        def f(x):
            if x > 0:
                x = add(100)[x]
            fi(x > 100)
            return x

        assert f[5] == 105
        assert f.rev[105] == 5
        assert f[-5] == -5
        assert f.rev[-5] == -5

    def test_if_custom_fi_with_else(self):
        @reversible
        def f(x):
            if x > 0:
                x = add(100)[x]
            else:
                x = move[x]
            fi(x > 100)
            return x

        assert f[5] == 105
        assert f.rev[105] == 5
        assert f[-5] == -5
        assert f.rev[-5] == -5

    def test_if_elif_else(self):
        @reversible
        def f(x, c1, c2):
            if c1:
                x = add(1)[x]
            elif c2:
                x = add(10)[x]
            else:
                x = add(100)[x]
            return x

        assert f(c1=True, c2=False)[0] == 1
        assert f(c1=False, c2=True)[0] == 10
        assert f(c1=False, c2=False)[0] == 100
        assert f(c1=True, c2=False).rev[1] == 0
        assert f(c1=False, c2=True).rev[10] == 0
        assert f(c1=False, c2=False).rev[100] == 0

    def test_if_nested(self):
        @reversible
        def f(x, c1, c2):
            if c1:
                if c2:
                    x = add(1)[x]
                else:
                    x = add(2)[x]
            else:
                x = add(3)[x]
            return x

        assert f(c1=True, c2=True)[0] == 1
        assert f(c1=True, c2=True).rev[1] == 0
        assert f(c1=True, c2=False)[0] == 2
        assert f(c1=True, c2=False).rev[2] == 0
        assert f(c1=False, c2=True)[0] == 3
        assert f(c1=False, c2=True).rev[3] == 0


# ============================================================
# 4. while/elihw
# ============================================================


class TestWhileElihw:
    def test_add_n_times(self):
        @reversible
        def add_n_times(x, a, n=10):
            i = init(0)[None]
            while i < n:
                x = add(a)[x]
                i = add(1)[i]
            elihw(i > 0)
            destroy(n)[i]
            return x

        assert add_n_times(a=1, n=10)[0] == 10
        assert add_n_times(a=1, n=10).rev[10] == 0
        assert add_n_times(a=2, n=5)[0] == 10
        assert add_n_times(a=2, n=5).rev[10] == 0

    def test_while_zero_iterations(self):
        @reversible
        def f(x, n):
            i = init(0)[None]
            while i < n:
                x = add(1)[x]
                i = add(1)[i]
            elihw(i > 0)
            destroy(n)[i]
            return x

        assert f(n=0)[10] == 10
        assert f(n=0).rev[10] == 10

    def test_while_nested(self):
        @reversible
        def f(x, n, m):
            i = init(0)[None]
            while i < n:
                j = init(0)[None]
                while j < m:
                    x = add(1)[x]
                    j = add(1)[j]
                elihw(j > 0)
                destroy(m)[j]
                i = add(1)[i]
            elihw(i > 0)
            destroy(n)[i]
            return x

        assert f(n=3, m=4)[0] == 12
        assert f(n=3, m=4).rev[12] == 0


# ============================================================
# 5. for
# ============================================================


class TestFor:
    def test_add_range(self):
        @reversible
        def add_range(x, n=10):
            for i in range(n):
                x = add(i)[x]
            return x

        assert add_range(n=10)[0] == 45
        assert add_range(n=10).rev[45] == 0
        assert add_range(n=0)[42] == 42
        assert add_range(n=0).rev[42] == 42

    def test_for_list(self):
        @reversible
        def f(x, items):
            for item in items:
                x = add(item)[x]
            return x

        assert f(items=[1, 2, 3])[0] == 6
        assert f(items=[1, 2, 3]).rev[6] == 0

    def test_for_tuple(self):
        @reversible
        def f(x, items):
            for item in items:
                x = add(item)[x]
            return x

        assert f(items=(1, 2, 3))[0] == 6
        assert f(items=(1, 2, 3)).rev[6] == 0

    def test_for_range(self):
        @reversible
        def f(x, n):
            for i in range(n):
                x = add(i)[x]
            return x

        assert f(n=5)[0] == 10
        assert f(n=5).rev[10] == 0

    def test_for_dict_keys(self):
        @reversible
        def f(x, d):
            for k in d:
                x = add(k)[x]
            return x

        d = {1: "a", 2: "b", 3: "c"}
        assert f(d=d)[0] == 6
        assert f(d=d).rev[6] == 0

    def test_for_reversed_list(self):
        # reversed(...) is stripped on the reverse pass
        @reversible
        def f(x):
            for item in reversed([1, 2, 3]):
                x = add(item)[x]
            return x

        assert f[0] == 6
        assert f.rev[6] == 0

    def test_for_with_unpacking(self):
        @reversible
        def f(x, items):
            for k, v in items:
                x = add(k)[x]
                x = add(v)[x]
            return x

        items = [(1, 10), (2, 20)]
        assert f(items=items)[0] == 33
        assert f(items=items).rev[33] == 0

    def test_for_nested(self):
        @reversible
        def f(x, n):
            for i in range(n):
                for j in range(n):
                    x = add(1)[x]
            return x

        assert f(n=3)[0] == 9
        assert f(n=3).rev[9] == 0

    def test_for_reverse_order_matters(self):
        # non-commutative operations: if reverse iterated in forward order,
        # the result would be wrong
        @reversible
        def f(x):
            for i in [1, 2]:
                x = add(i)[x]
                x = mult(2)[x]
            return x

        # forward: 0 -> 1 -> 2 -> 4 -> 8
        assert f[0] == 8
        # reverse must undo in reverse order: 8 -> 4 -> 2 -> 1 -> 0
        assert f.rev[8] == 0


# ============================================================
# 6. Scopes
# ============================================================


class TestScopes:
    def test_closure_mutation_list(self):
        acc = [0]

        add_inplace = ReversibleFunction(
            lambda none, a: acc.__setitem__(0, acc[0] + a) or None,
            lambda none, a: acc.__setitem__(0, acc[0] - a) or None,
        )

        @reversible
        def inc_three(y):
            i = init(0)[None]
            while i < 3:
                add_inplace(1)[None]
                y = add(1)[y]
                i = add(1)[i]
            elihw(i > 0)
            destroy(3)[i]
            return y

        out = inc_three[0]
        assert out == 3
        assert acc[0] == 3
        back = inc_three.rev[out]
        assert back == 0
        assert acc[0] == 0


# ============================================================
# 7. Arbitrary lines
# ============================================================


class TestArbitraryLines:
    def test_print_runs_on_both_passes(self, capsys):
        @reversible
        def f(x, n=3):
            i = init(0)[None]
            while i < n:
                x = add(1)[x]
                i = add(1)[i]
                print(x, end=" ")
            elihw(i > 0)
            destroy(n)[i]
            return x

        out = f(n=3)[0]
        assert capsys.readouterr().out.strip() == "1 2 3"
        back = f(n=3).rev[out]
        assert capsys.readouterr().out.strip() == "3 2 1"
        assert back == 0

    def test_assert_runs_on_both_passes(self):
        @reversible
        def f(x):
            x = add(1)[x]
            assert x != 100
            return x

        assert f[5] == 6
        assert f.rev[6] == 5


# ============================================================
# 8. Compilation errors
# ============================================================


class TestCompilationErrors:
    def test_return_not_last(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                y = move[x]
                return y
                z = move[y]

    def test_return_inside_if(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x, c):
                if c:
                    return x
                else:
                    return x

    def test_return_inside_while(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                while x > 0:
                    return x
                elihw(x > 0)

    def test_return_inside_for(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                for i in range(3):
                    return x
                return x

    def test_return_tuple(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x, y):
                return x, y

    def test_return_expression(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                return move[x]

    def test_use_after_destroy(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x, a, b):
                y = mult(a)[x]
                z = add(b)[x]  # x already destroyed
                return z

    def test_assign_to_existing(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                x = 42
                return x

    def test_if_inconsistent_lifetime(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x, c):
                if c:
                    y = add(1)[x]
                return y

    def test_if_destroy_only_in_one_branch(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x, c):
                if c:
                    y = move[x]
                else:
                    pass
                return y

    def test_while_create_in_body(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x, n):
                i = init(0)[None]
                while i < n:
                    y = add(1)[x]
                    i = add(1)[i]
                elihw(i > 0)
                destroy(n)[i]
                return y

    def test_missing_elihw(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                i = init(0)[None]
                while i < 10:
                    x = add(1)[x]
                    i = add(1)[i]
                destroy(10)[i]
                return x

    def test_fi_with_no_args(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x, c):
                if c:
                    x = add(1)[x]
                fi()
                return x

    def test_fi_with_two_args(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x, c):
                if c:
                    x = add(1)[x]
                fi(c, c)
                return x

    def test_break(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                i = init(0)[None]
                while i < 10:
                    if i > 3:
                        break
                    x = add(1)[x]
                    i = add(1)[i]
                elihw(i > 0)
                return x

    def test_continue(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                i = init(0)[None]
                while i < 10:
                    i = add(1)[i]
                    if i > 3:
                        continue
                    x = add(1)[x]
                elihw(i > 0)
                return x

    def test_while_else(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                i = init(0)[None]
                while i < 3:
                    x = add(1)[x]
                    i = add(1)[i]
                else:
                    pass
                elihw(i > 0)
                return x

    def test_for_else(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                for i in range(3):
                    x = add(1)[x]
                else:
                    pass
                return x

    def test_try_except(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                try:
                    y = add(1)[x]
                except Exception:
                    pass
                return y

    def test_with(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                with open(__file__):
                    pass
                return x

    def test_yield(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                yield x

    def test_class_inside(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                class C:
                    pass
                return x

    def test_def_inside(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                def g(y):
                    return y
                return x

    def test_global(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                global SOME_GLOBAL
                return x

    def test_nonlocal(self):
        def outer():
            val = 0
            with pytest.raises(RevpyCompilationError):
                @reversible
                def inner(y):
                    nonlocal val
                    return y
            return val

        outer()

    def test_non_name_in_brackets(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                arr = [0]
                y = add(1)[arr[0]]
                return y

    def test_attribute_assignment(self):
        with pytest.raises(RevpyCompilationError):
            @reversible
            def f(x):
                class P:
                    pass
                p = P()
                p.x = move[x]
                return x


# ============================================================
# 9. Runtime errors
# ============================================================


class TestRuntimeErrors:
    def test_destroy_wrong_value(self):
        assert destroy(42)[42] is None
        with pytest.raises(ReversibilityError):
            destroy(42)[41]

    def test_destroy_float_wrong_value(self):
        with pytest.raises(ReversibilityError):
            destroy_float(1.0)[2.0]

    def test_destroy_float_within_tolerance(self):
        # within default np.isclose tolerance — no error
        assert destroy_float(1.0)[1.0 + 1e-9] is None

    def test_while_wrong_elihw_forward(self):
        @reversible
        def f(x, n):
            i = init(0)[None]
            while i < n:
                x = add(1)[x]
                i = add(1)[i]
            elihw(i > 1000)  # never true during the loop
            destroy(n)[i]
            return x

        with pytest.raises(ReversibilityError):
            f(n=10)[0]

    def test_if_default_fi_broken(self):
        # Default fi(condition) => reversibility_assert(condition) runs in
        # the forward path after the branch body. Since x changed, the
        # condition no longer holds, and forward fails immediately.
        @reversible
        def f(x):
            if x > 0:
                x = add(-1)[x]
            return x

        with pytest.raises(ReversibilityError):
            f[1]