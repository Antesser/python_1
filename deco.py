#!/usr/bin/env python
# -*- coding: utf-8 -*-

from functools import update_wrapper, wraps


def disable(decorator):
    '''
    Disable a decorator by re-assigning the decorator's name
    to this function. For example, to turn off memoization:

    >>> memo = disable

    '''
    return decorator


def decorator(decorator):
    """
    Decorate a decorator so that it inherits the docstrings
    and stuff from the function it's decorating.
    """

    def wrapper(func):
        return update_wrapper(func, decorator)

    return wrapper


def countcalls(func):
    """Decorator that counts calls made to the function decorated."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        wrapper.calls += 1
        result = func(*args, **kwargs)
        update_wrapper(wrapper, func)
        return result

    wrapper.calls = 0
    return wrapper


def memo(func):
    """
    Memoize a function so that it caches all return values for
    faster future lookups.
    """
    vault = dict()

    @wraps(func)
    def wrapper(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in vault:
            result = func(*args, **kwargs)
            vault[key] = result
        else:
            result = vault[key]
        update_wrapper(wrapper, func)
        return result

    return wrapper


def n_ary(func):
    """
    Given binary function f(x, y), return an n_ary function such
    that f(x, y, z) = f(x, f(y,z)), etc. Also allow f(x) = x.
    """

    @wraps(func)
    def wrapper(first, second, *args):
        if not args:
            result = func(first, second)
        else:
            result = func(first, wrapper(second, *args))
        update_wrapper(wrapper, func)
        return result

    return wrapper


def trace(prefix):
    """Trace calls made to function decorated."""

    def wrap(func):
        @wraps(func)
        def wrapper(*args):
            print(
                f"{prefix * wrapper.count}-->{func.__name__}({",".join(str(arg) for arg in args)})"
            )
            wrapper.count += 1
            result = func(*args)
            wrapper.count -= 1
            print(
                f"{prefix * wrapper.count}-->{func.__name__}({",".join(str(arg) for arg in args)}) == {result}"
            )
            update_wrapper(wrapper, func)
            return result

        wrapper.count = 0
        return wrapper

    return wrap


@memo
@countcalls
@n_ary
def foo(a, b) -> int:
    return a + b


@countcalls
@memo
@n_ary
def bar(a, b) -> int:
    return a * b


@countcalls
@trace("####")
@memo
def fib(n) -> int:
    """Some doc"""
    return 1 if n <= 1 else fib(n - 1) + fib(n - 2)


def main() -> None:
    print(foo(4, 3))
    print(foo(4, 3, 2))
    print(foo(4, 3))
    print("foo was called", foo.calls, "times")

    print(bar(4, 3))
    print(bar(4, 3, 2))
    print(bar(4, 3, 2, 1))
    print("bar was called", bar.calls, "times")

    print(fib.__doc__)
    fib(3)
    print(fib.calls, "calls made")


if __name__ == "__main__":
    main()
