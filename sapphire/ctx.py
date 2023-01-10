#!/usr/bin/env python

from typing import Optional, Tuple, List, Dict, Set, Callable, Iterable, Union
from base64 import b64decode
import zlib
import pickle
import sys
import subprocess
import io
from math import ceil, log2
from functools import reduce
from abc import ABC, abstractmethod

class Context:
    def __init__(self):
        self._next_id = 0
        self._constraints = []
        self._values = {}
        self._true = Variable(self)
        self.ensure(self._true)

    def _get_next_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _add(self, *terms):
        self._constraints.append(terms)

    def ensure(self, variable: "Variable"):
        self._add(variable._id)

    def export_dimacs(self, file=sys.stdout):
        print("p cnf {} {}".format(self._next_id, len(self._constraints)), file=file)
        for c in self._constraints:
            print(" ".join(map(lambda x: str(x), c)), 0, file=file)

    def import_dimacs(self, file=sys.stdin):
        lines = filter(lambda x: len(x) > 0 and x[0] != "c", file.read().strip().split("\n"))
        for line in lines:
            line = line.strip().split(" ")
            if line[0] == "v":
                for i in line[1:]:
                    n = int(i)
                    if n == 0:
                        continue
                    self._values[abs(n)] = (n > 0)

class Variable:
    def __init__(self, ctx: Context, id: Optional[int] = None):
        self._ctx = ctx
        self._id = id or ctx._get_next_id()

    def value(self) -> Optional[bool]:
        return self._ctx._values.get(self._id, None)

    def __invert__(self):
        return Variable(self._ctx, -self._id)

    def __and__(self, other: Union["Variable", bool]) -> "Variable":
        if isinstance(other, bool):
            return self if other else ~self._ctx._true
        return and_op(2)(self, other)[0]

    def __or__(self, other: Union["Variable", bool]) -> "Variable":
        if isinstance(other, bool):
            return self._ctx._true if other else self
        return or_op(2)(self, other)[0]

    def __xor__(self, other: Union["Variable", bool]) -> "Variable":
        if isinstance(other, bool):
            return ~self if other else self
        return xor2(self, other)[0]

    def __eq__(self, other: Union["Variable", bool]) -> "Variable": # type: ignore[override]
        return ~(self != other)

    def __ne__(self, other: Union["Variable", bool]) -> "Variable": # type: ignore[override]
        return self ^ other

class Natural:
    optimize = True

    def __init__(self, ctx: Context, n_bits: Optional[int] = None, bits: Optional[List[Variable]] = None, number: Optional[int] = None, max_value: Optional[int] = None):
        self._ctx = ctx
        if bits is not None:
            self._bits = bits
            self._max_value = max_value if max_value is not None else (2 ** len(bits)) - 1
        else:
            if number is not None:
                if n_bits is None:
                    n_bits = Natural._req(number)
                self._max_value = number
                self._bits = []
                for i in range(n_bits):
                    if (number & 1) == 1:
                        self._bits.append(ctx._true)
                    else:
                        self._bits.append(~ctx._true)
                    number >>= 1
                assert number == 0
            else:
                assert n_bits is not None
                self._bits = [Variable(ctx) for i in range(n_bits)]
                self._max_value = (2 ** n_bits) - 1

    def value(self) -> Optional[int]:
        if any(i.value() is None for i in self._bits):
            return None
        n = 0
        for i in reversed(self._bits):
            n <<= 1
            n |= int(i.value())
        return n

    def get_bit(self, b: int) -> Variable:
        return self._bits[b]

    @staticmethod
    def level(a: "Natural", b: "Natural") -> Tuple["Natural", "Natural"]:
        if a.size() == b.size():
            return (a, b)
        elif a.size() < b.size():
            return (a.extend(b.size()), b)
        else:
            return (a, b.extend(a.size()))

    @staticmethod
    def _req(a: int) -> int:
        return int(ceil(log2(a + 1)))

    def size(self) -> int:
        return len(self._bits)

    def extend(self, n_bits: int) -> "Natural":
        if n_bits <= self.size():
            return self
        return Natural(self._ctx, bits=(self._bits + [~self._ctx._true for i in range(self.size(), n_bits)]), max_value=self._max_value)

    def truncate(self, n_bits: int, force: bool = False) -> "Natural":
        if n_bits >= self.size():
            return self
        if force:
            for i in range(n_bits, self.size()):
                self._ctx.ensure(~self._bits[i])
        return Natural(self._ctx, bits=self._bits[:n_bits], max_value=min(self._max_value, 2 ** n_bits))

    def __invert__(self):
        bits = [~self.get_bit(i) for i in range(self.size())]
        return Natural(self._ctx, bits=bits)

    def __xor__(self, other):
        if isinstance(other, int):
            other = Natural(self._ctx, number=other)
        a, b = Natural.level(self, other)
        bits = [a.get_bit(i) ^ b.get_bit(i) for i in range(a.size())]
        return Natural(self._ctx, bits=bits)

    def __eq__(self, other):
        if isinstance(other, int):
            other = Natural(self._ctx, number=other)
        a, b = Natural.level(self, other)
        return c_all(*[a._bits[i] == b._bits[i] for i in range(a.size())])

    def __ne__(self, other):
        if isinstance(other, int):
            other = Natural(self._ctx, number=other)
        a, b = Natural.level(self, other)
        return c_any(*[a._bits[i] != b._bits[i] for i in range(a.size())])

    def __mul__(self, other):
        if isinstance(other, int):
            other = Natural(self._ctx, number=other)
        a, b = self, other
        if a.size() < b.size():
            a, b = b, a
        result = []
        prev = Natural(self._ctx, bits=[x & b.get_bit(0) for x in a._bits], max_value=a._max_value)
        result.append(prev.get_bit(0))
        prev = Natural(self._ctx, bits=prev._bits[1:], max_value=(prev._max_value // 2))
        for i in range(1, b.size()):
            num = Natural(self._ctx, bits=[x & b.get_bit(i) for x in a._bits], max_value=a._max_value)
            next = prev + num
            result.append(next.get_bit(0))
            prev = Natural(self._ctx, bits=next._bits[1:], max_value=(next._max_value // 2))
        bits = result + prev._bits
        while len(bits) > Natural._req(a._max_value * b._max_value):
            bits.pop()
        return Natural(self._ctx, bits=bits, max_value=(a._max_value * b._max_value))

    def __add__(self, other):
        if isinstance(other, int):
            other = Natural(self._ctx, number=other)
        a, b = Natural.level(self, other)
        bits = []
        carry = ~self._ctx._true
        step = 1
        if Natural.optimize:
            step = 3
        for i in range(0, a.size(), step):
            acc = []
            for j in range(i, min(a.size(), i + step)):
                acc.append(a._bits[j])
            for j in range(i, min(a.size(), i + step)):
                acc.append(b._bits[j])
            acc.append(carry)
            res = list(sum_base[(len(acc) - 1) // 2](*acc))
            carry = res.pop()
            bits += res
        bits.append(carry)
        while len(bits) > Natural._req(a._max_value + b._max_value):
            bits.pop()
        return Natural(self._ctx, bits=bits, max_value=(a._max_value + b._max_value))

    def __lt__(self, other):
        if isinstance(other, int):
            other = Natural(self._ctx, number=other)
        a, b = Natural.level(self, other)
        base = ~self._ctx._true
        for i in range(a.size()):
            base = lt(a._bits[i], b._bits[i], base)[0]
        return base

    def __le__(self, other):
        if isinstance(other, int):
            other = Natural(self._ctx, number=other)
        a, b = Natural.level(self, other)
        base = self._ctx._true
        for i in range(a.size()):
            base = lt(a._bits[i], b._bits[i], base)[0]
        return base

    def __gt__(self, other):
        if isinstance(other, int):
            other = Natural(self._ctx, number=other)
        a, b = Natural.level(self, other)
        base = ~self._ctx._true
        for i in range(a.size()):
            base = gt(a._bits[i], b._bits[i], base)[0]
        return base

    def __ge__(self, other):
        if isinstance(other, int):
            other = Natural(self._ctx, number=other)
        a, b = Natural.level(self, other)
        base = self._ctx._true
        for i in range(a.size()):
            base = gt(a._bits[i], b._bits[i], base)[0]
        return base

    def __lshift__(self, other):
        assert isinstance(other, int)
        return Natural(self._ctx, bits=([~self._ctx._true] * other + self._bits), max_value=(self._max_value << other))

    def __rshift__(self, other):
        assert isinstance(other, int)
        return Natural(self._ctx, bits=self._bits[other:], max_value=(self._max_value >> other))

    def __or__(self, other):
        if isinstance(other, int):
            other = Natural(self._ctx, number=other)
        a, b = Natural.level(self, other)
        return Natural(self._ctx, bits=[a._bits[i] | b._bits[i] for i in range(a.size())])

    def __and__(self, other):
        if isinstance(other, int):
            other = Natural(self._ctx, number=other)
        a, b = Natural.level(self, other)
        return Natural(self._ctx, bits=[a._bits[i] & b._bits[i] for i in range(a.size())])

class Operator(ABC):
    def __init__(self, input: int, output: int):
        assert input > 0 and output > 0
        self.input = input
        self.output = output

    def __call__(self, *args: Variable) -> Tuple[Variable, ...]:
        assert len(args) == self.input
        ctx = args[0]._ctx
        assert all(i._ctx is ctx for i in args)
        output = tuple(Variable(ctx) for _ in range(self.output))
        self._call(ctx, *map(lambda x: x._id, args + output))
        return output

    @abstractmethod
    def _call(self, ctx: Context, *args: int):
        pass

def get_cnf(*args, **kwargs):
    raise Exception("Not implemented")

class Blueprint(Operator):
    def __init__(self, input: int, output: int, f: Optional[Callable[..., Optional[bool]]] = None, cache: Optional[str] = None):
        super().__init__(input, output)
        self._cnf = pickle.loads(zlib.decompress(b64decode(cache))) if cache is not None else (get_cnf(input + output, f) if f is not None else None)
        assert self._cnf is not None

    def _call(self, ctx: Context, *args: int):
        for c in self._cnf:
            assert len(c) == len(args)
            clause = []
            for i, v in enumerate(c):
                if v is not None:
                    clause.append(args[i] if v else -args[i])
            ctx._add(*clause)

class Procedural(Operator):
    def __init__(self, input: int, output: int, f: Callable[..., Iterable[Tuple[int, ...]]]):
        super().__init__(input, output)
        self._f = f

    def _call(self, ctx: Context, *args: int):
        for i in self._f(*args):
            ctx._add(*i)

def c_sum(*x: Natural) -> Natural:
    return reduce(lambda y, z: y + z, x, Natural(x[0]._ctx, bits=[~x[0]._ctx._true], max_value=0))

def and_op(n: int) -> Procedural:
    def f(*x: int) -> List[Tuple[int, ...]]:
        out = []
        out.append((x[-1],) + tuple(map(lambda y: -y, x[:-1])))
        for i in x[:-1]:
            out.append((-x[-1], i))
        return out
    return Procedural(n, 1, f)

def c_all(*x: Variable) -> Variable:
    return and_op(len(x))(*x)[0]

def or_op(n: int) -> Procedural:
    def f(*x: int) -> List[Tuple[int, ...]]:
        out = []
        out.append((-x[-1],) + x[:-1])
        for i in x[:-1]:
            out.append((x[-1], -i))
        return out
    return Procedural(n, 1, f)

def c_any(*x: Variable) -> Variable:
    return or_op(len(x))(*x)[0]

def exactly_one_op(n: int) -> Procedural:
    def f(*x: int) -> List[Tuple[int, ...]]:
        out = []
        for i in range(len(x)):
            out.append(tuple(-x[j] if i == j else x[j] for j in range(len(x))))
        for i in range(len(x) - 1):
            for j in range(i + 1, len(x) - 1):
                out.append((-x[i], -x[j], -x[-1]))
        return out
    return Procedural(n, 1, f)

def exactly_one(*x: Variable) -> Variable:
    return exactly_one_op(len(x))(*x)[0]

def at_most_one_op(n: int) -> Procedural:
    def f(*x: int) -> List[Tuple[int, ...]]:
        out = []
        for i in range(len(x) - 1):
            out.append(tuple(x[j] for j in range(len(x)) if j != i))
        for i in range(len(x) - 1):
            for j in range(i + 1, len(x) - 1):
                out.append((-x[i], -x[j], -x[-1]))
        return out
    return Procedural(n, 1, f)

def at_most_one(*x: Variable) -> Variable:
    return at_most_one_op(len(x))(*x)[0]

xor2 = Blueprint(2, 1, cache="eNprYJkqyQABsVM0Ojs62qd0dIKIjs72KZ2dQCJVDwDMFA2x")

full_adder = Blueprint(3, 2, cache="eNolyKEVgEAMA1AEw1QxShwSeRvcAMjEl31JXyryk77ndx+5p6soEruLLpEapWyTTUWAtE5o9Hs24bZ7XT/MBCZx")

imply = Blueprint(2, 1, cache="eNprYJkqwgABsVM0Ojs626d0+HW0T/HrBBKpegCF9wqC")

lt = Blueprint(3, 1, cache="eNprYJmqzwABsVM0NDo6/TpKpmh0+HWCKL+Ojk4Q1QnmAaVAvE6gZMmUVD0AKGkVgg==")

gt = Blueprint(3, 1, cache="eNprYJmqzwABsVM0NDo7/DpKpmj4dXSCKCCnE0h1+oF5QBLE6wByS6ak6gEAKGkVgg==")

sum_bits = {
    2: Blueprint(2, 2, cache="eNprYJmqzwABsVM0NDo7OvxKpmh0dEKojk4Q1dnp1wGk/Dr8OkGUXyeQStUDACT3FQ0="),
    3: Blueprint(3, 2, cache="eNolyKEVgEAMA1AEw1QxShwSeRvcAMjEl31JXyryk77ndx+5p6soEruLLpEapWyTTUWAtE5o9Hs24bZ7XT/MBCZx"),
    4: Blueprint(4, 3, cache="eNpFjbERgDAMAykYJhWjaANKNmAASqkPo9Ij2yG4SP78kXKt97PU7L010QOcvVGTaP6ISpI0rKhhEUsw7XznqEbfJOPXglhWnzkJ7mD2WRX5ZFlEkvkHoKLsGAnGg0jgpxiFjXuS9dmP7QWOEGr1"),
    5: Blueprint(5, 3, cache="eNpNkMERwkAMA2GGYu5FKe6AJx1QAE/rH9qjFiT57OC5mawVS77kfft8rxfX41gLqYp4HYtPnEgeTBgB9CwJJ86s5VJTzVYHHbDDFICxNTqibWxabYQqB/9uhskFJrcxdFseqaGPQOVGIzN5cqt0GfVawYXWK6FV/49ClCu9reIKqfZAoFCejbCv1dAa24ptk16qNrPzHUIM2wQbVSA+7z9ekdK3"),
    6: Blueprint(6, 3, cache="eNpVkrF1AzEMQ/2ePcxVHoUbuMwGGSCl0Dujuo8IkIRy1ScFUiB1P4/fz/3G7/W+Lix+Ed/va+FgBcWMhndgXiAD1mMxqJ7mJFjjnsCRZ3H7wamfe2EmwXp7Aw5NRjNjsyzDfYplDe5jTR65jzXDamnNsC72PjF727SHLA4MB4a5xdltc7DYtX4LDm/9eDZLDr/FeDZT4Vnwz/M2TQ9RPwrnihyl8zxoXmjN9n4wa1KzQsvKfByc+oO3HOU5eZXnYYoX7AHNtSD6pxyV17K6Fq3Jp4jWZ1YcGOai0P71eqXn03Rt5HC6KzgaObQK7W2TOGt5VnoMM5jaSBPynMN0H8mkyaZoTYi/nn+LjMZP"),
    7: Blueprint(7, 3, cache="eNpVlLFxQzEMQ1OkyF0WcZVRuEHKbJABUhJ9sm9EgBRhn32nZ5EQSOr/n9e/97cXfj5/Hw+kPhHfv4+EQwoHSBeKFg4ZJAgAXBqrhoSpweAsYDsGXMEEDCR3cxyo0N7gIEMrfUvog1Z6dxwYt2Hc3HOsIYCHFW6vYTkXum3YSgcS8B1JmJ0bJj2zc0G2zY7lLEgBO3p4zkG7LrCcBTV47sHTGK3xiYUEfCTeXlhHKbAdFe4V8yYCsPtmYb4jC3vfbCQLXQHMzoWnjsIA1sSuAGbUBgzbeeo1YCNZaAN76ILONDUbFmDDWmgxu2J3chKDPVkm4GF0Z0+Wj96baCW4A7ia1tZR82bSca4K3yh9E6OwoP4NzA4vHgaUAUkrSDn9Dpow3rC8r8GTsdJsdu3wxAEZMDhJuA4GQk8C2vUphfJdz/mhz6GB3jkFiPsxO24aWBkGSgCTA9CPOlqLzHbNgTRUGCas5NBhYM8g0PkDKQnM5ALdeK4vBLFHAgNOEBcCF+gfPZ/s5bVTR/ah6vQUR/E9Z3rdxwyAQ+gpcNnAKcaJVUc5LUH9mw2hKAhqmQ2Mrx5i6qm9lJ3g1RGEBpfdHQUSmhgW6twFehBQL3LUmNICpAkLXTi55hdTHANVgpIKvj7+Adu9pxQ=")
}

boolmatmul = {
    1: Blueprint(2, 1, cache="eNprYJkqwgABsVM0Ojs72qf4dXS2T+nwAxKpegCGAQqD"),
    2: Blueprint(4, 1, cache="eNprYJlqygABsVM0NPw6/Do6S6YA6Q4/EN3hB+EDhcH8zk6gAEjer7MTSKfqAQCduBdb"),
    3: Blueprint(6, 1, cache="eNprYJlazAABsVM0NPw6QLCzZAqY1eEHYXX4wcRA0iAWSAQiBmLBxGDqwIaAxTo7/YCgA6TXD8SGsEBsICtVDwCN0jEX"),
    4: Blueprint(8, 1, cache="eNpFjbERgDAMAykYJhWjeANKNmAASqcPo9IT8fjkNK+Pzr7W+1mYfbQWyevn+DmjOMNeX7BsebG9+ywV08bD9tWHy3s/bO++9/ce36TuBgkmFStNPrYXLIVnQw=="),
    5: Blueprint(10, 1, cache="eNo9z8cRwjAARFHA5JxzDjN7ohR1wJECPEMBHK2uEQu79sVfz0rv7JGXgFDoja+87CxCygoU1MxJrUJGrTmpdehXasNJbUIzqS0ntQ0tRO04qV1oXWrPSe1D21AHTuoQ2pU6clLH0CGoEyd1Cp2JOnNS59ARqQsndQmdmLpyUtfQBagbJ3UL3Ye6c1L30PWoByf1iBjD/yle+QkhaCDlGd+P30DKC37yHUh5hWbGmPL2vH8AFRbWvw=="),
}

sum_base = {
    1: Blueprint(3, 2, cache="eNolyKEVgEAMA1AEw1QxShwSeRvcAMjEl31JXyryk77ndx+5p6soEruLLpEapWyTTUWAtE5o9Hs24bZ7XT/MBCZx"),
    2: Blueprint(5, 3, cache="eNo1jrENxDAMA/NA2uzh6kfRBimzQQb4kuzz+0YkbRuwKZs68bf/j8/mdT5jENUbdT+jCKiShCQjCebVNyNlpA19chKoHnDCuAjstbi0PTBOAgKI9IQl2zTjdFHMtNJHMpQYetWdtvIAG5g0Tpa4NpT/ESlsE67vC5jZcg0="),
    3: Blueprint(7, 4, cache="eNo9kMdtREEMQ22vc845RzrApUwHPrqAAX4BPkpdW6Q0u/jAguLoSdTf7KcvANbczFpr1qa+GNJSesglsOzmJncGlsN2yWW5kny8gii7D9Rqkr1Qa+p1L9R6kinpbiTZC7UJPfVCbSV5oLbROIUf3R3En+XbkLuQw9mUe3IzUMj9DNj486kfgAvY6D1UrxahPIK4LHHQcZHNhTqBuHS51WleQx1BPgPLHKolz9GkaquLvEbmmPoleFIfS17psQ5PeZ15WeKgG7g3n+e9zVspUaDu5M7z3tfc2vkhE3nt/Agfd6T7BBsbUz6jruySL5lIc2PQa8bXoMj7huJmL4rs2fte5JIfqEbOmvonCssHU//6/f4HpRT55Q==")
}
