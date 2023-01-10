#!/usr/bin/env pypy3

from io import StringIO
from sapphire import *
from sapphire.ctx import exactly_one
from math import ceil, log2
from enum import Enum, auto
from sys import argv, stderr

class SatModelMethod(Enum):
    STANDARD = auto()
    EXONE = auto()
    HOLES = auto()

def eprint(*args, **kwargs):
    return print(*args, **kwargs, file = stderr)

def SatModel(model, method = SatModelMethod.STANDARD, solution = None):
    Natural.optimize = False
    ctx = Context()
    f = StringIO(model)
    n, m = map(int, f.readline().strip().split(" "))
    mapp = {}
    inverse = []
    for i in range(n):
        s = f.readline().strip().split(" ")
        assert s[1] == "c"
        mapp[s[0]] = i
        inverse.append(s[0])
    clauses = []
    maximum = 0
    for j in range(m):
        clause = []
        s = f.readline().strip().split(" ")
        assert s[1] == "f"
        assert int(s[0]) * 4 + 2 == len(s)
        for i in range(2, len(s), 4):
            clause.append((mapp[s[i + 1]], mapp[s[i]], None if s[i + 2] == "-inf" else int(s[i + 2]), None if s[i + 3] in ("inf", "+inf") else int(s[i + 3])))
            maximum = max(maximum, abs(clause[-1][2] or 0), abs(clause[-1][3] or 0))
        clauses.append(clause)
    maximum *= n * 2
    b = ceil(log2(maximum + 1)) + 1
    v = [Natural(ctx, b) for i in range(n)]
    for i in v:
        ctx.ensure(~i.get_bit(b - 1))
    vn = [((~v[i]) + 1).truncate(b) for i in range(n)]
    store = dict()
    for clause in clauses:
        cond = []
        hcond = []
        for j, a in enumerate(sorted(clause, key = lambda x: x[3] or float("-inf"))):
            if (a[0], a[1]) not in store:
                ab = (v[a[0]] + vn[a[1]]).truncate(b)
                ba = (vn[a[0]] + v[a[1]]).truncate(b)
                store[(a[0], a[1])] = (ab, ba)
            ab, ba = store[(a[0], a[1])]
            scond = []
            if method in (SatModelMethod.STANDARD, SatModelMethod.EXONE):
                if a[2] is not None:
                    if a[2] >= 0:
                        scond.append((ab >= a[2]) & ~ab.get_bit(b - 1))
                    else:
                        scond.append(((ba <= -a[2]) & ~ba.get_bit(b - 1)) | ba.get_bit(b - 1))
                if a[3] is not None:
                    if a[3] >= 0:
                        scond.append(((ab <= a[3]) & ~ab.get_bit(b - 1)) | ab.get_bit(b - 1))
                    else:
                        scond.append((ba >= -a[3]) & ~ba.get_bit(b - 1))
            elif method == SatModelMethod.HOLES:
                if j == 0 and a[2] is not None:
                    if a[2] >= 0:
                        hcond.append((ab >= a[2]) & ~ab.get_bit(b - 1))
                    else:
                        hcond.append(((ba <= -a[2]) & ~ba.get_bit(b - 1)) | ba.get_bit(b - 1))
                elif j == len(clause) - 1 and a[3] is not None:
                    if a[3] >= 0:
                        hcond.append(((ab <= a[3]) & ~ab.get_bit(b - 1)) | ab.get_bit(b - 1))
                    else:
                        hcond.append((ba >= -a[3]) & ~ba.get_bit(b - 1))
                if a[2] is not None:
                    if a[2] >= 0:
                        scond.append(((ab <= a[2]) & ~ab.get_bit(b - 1)) | ab.get_bit(b - 1))
                    else:
                        scond.append((ba >= -a[2]) & ~ba.get_bit(b - 1))
                if a[3] is not None:
                    if a[3] >= 0:
                        scond.append((ab >= a[3]) & ~ab.get_bit(b - 1))
                    else:
                        scond.append(((ba <= -a[3]) & ~ba.get_bit(b - 1)) | ba.get_bit(b - 1))
            else:
                raise NotImplementedError()
            if method == SatModelMethod.STANDARD:
                cond.append(c_all(*scond))
            elif method == SatModelMethod.EXONE:
                cond.append(exactly_one(*scond))
            elif method == SatModelMethod.HOLES:
                cond.append(c_any(*scond))
            else:
                raise NotImplementedError()
        if method == SatModelMethod.HOLES:
            ctx.ensure(c_all(*(cond + hcond)))
        else:
            ctx.ensure(c_any(*cond))
    if solution is None:
        out = StringIO()
        ctx.export_dimacs(out)
        return out.getvalue()
    else:
        ctx.import_dimacs(StringIO(solution))
        sol = {}
        for i in range(n):
            if v[i].value() is None:
                return None
            sol[inverse[i]] = v[i].value()
        return sol

if __name__ == "__main__":
    solution = SatModel(open(argv[1], "r").read())
    print(f"{solution}")
