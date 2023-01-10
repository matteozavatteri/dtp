from math import ceil, log2
from io import StringIO
import math
import argparse
import time
import os
from conf import *
from sat import *
import subprocess
import shlex

def LoadDtp(filename):
    #print("{}".format(filename))
    TimePoints  = set()
    Constraints = []
    W = 1

    with open(filename,"r") as tnfile:
        f = StringIO(tnfile.read())

    [N, M] = f.readline().strip().split()
    N = int(N)
    M = int(M)
    for i in range(0,N):
        [X, T] = f.readline().strip().split()
        assert (T == "c")
        TimePoints.add(X)
    for i in range(0,M):
        line = f.readline().strip().split()
        D = int(line[0])
        Constraints.append([])
        assert (line[1] == "f")
        for j in range(1,D+1):
            # 4*(j-1) + 2 = 4*j - 2
            # 4*(j-1) + 6 = 4*j + 2
            (X,Y,l,u) = tuple(line[4*j-2: 4*j+2])
            if l == "-inf":
                l = -math.inf
            else:
                l = int(l)
                W = max(W, abs(l))
            if u == "+inf":
                u = math.inf
            else:
                u = int(u)
                W = max(W, abs(u))
            Constraints[-1].append((Y,X,l,u))
            assert l <= u
        assert len(Constraints[-1]) == D

    assert len(TimePoints)  == N
    assert len(Constraints) == M
    return TimePoints, Constraints, W*N

# Be aware: Y - X \in [x1,y1] OR X - Y \in [x2,y2] will be undetected
# Remeber to respect the order in tn file
def TcspConstraint(disj):
    (Y,X,l,u) = disj[0]
    for (Yi,Xi,l,u) in disj[1:]:
        if Y != Yi or X != Xi:
            return False
    return True

def IsTCSP(Constraints):
    for c in Constraints:
        if not TcspConstraint(c):
            return False
    return True


def Tn(TimePoints, Constraints):
    text = StringIO()
    text.write("{} {}".format(len(TimePoints), len(Constraints)))
    for X in sorted(TimePoints):
        text.write("\n{} c".format(X))

    for DisjConstraint in Constraints:
        text.write("\n{} f".format(len(DisjConstraint)))
        for (Y,X,l,u) in DisjConstraint:
            if u == math.inf:
                u = "+inf"
            text.write(" {} {} {} {}".format(X,Y,l,u)) # recall, X -> Y (graph notation, that's why they are swapped)

    return text



def MiniZincNaiveEncoder(TimePoints, Constraints, H):
    mzn = StringIO()
    NameMap = dict()

    for X in TimePoints:
        NameMap[X] = len(NameMap)+1

    mzn.write("array[1..{}] of var 0..{}: X;\n".format(len(NameMap), H))

    for disj in Constraints:
        atoms = []
        for (Y,X,l,u) in disj:
            assert l != -math.inf or u != math.inf
            tmp = []
            if l != -math.inf:
                tmp.append("X[{Y}] - X[{X}] >= {l}".format(Y=NameMap[Y],X=NameMap[X],l=l))
            if u != math.inf:
                tmp.append("X[{Y}] - X[{X}] <= {u}".format(Y=NameMap[Y],X=NameMap[X],u=u))
            atoms.append("({})".format(" /\ ".join(tmp)))
        mzn.write("constraint {};\n".format(" \/ ".join(atoms)))

    mzn.write("output[\"(sat)\"];\n")
    mzn.write("solve satisfy;")

    return mzn.getvalue()

def MiniZincSwitchEncoder(TimePoints, Constraints, H, tcsp=False):
    if tcsp:
        assert IsTCSP(Constraints)

    mzn = StringIO()
    NameMap = dict()

    for X in TimePoints:
        NameMap[X] = len(NameMap)+1

    mzn.write("array[1..{}] of var 0..{}: X;\n".format(len(NameMap), H))
    
    for i in range(0,len(Constraints)):
        D = len(Constraints[i])
        if D > 1:
            mzn.write("array[1..{}] of var bool: s{};\n".format(D,i));

    for i in range(0,len(Constraints)):
        D = len(Constraints[i])
        for j in range(0,len(Constraints[i])):
            mzn.write("constraint ")
            if D > 1:
                mzn.write("if s{}[{}] then ".format(i,j+1))

            (Y,X,l,u) = Constraints[i][j]
            assert l != -math.inf or u != math.inf
            tmp = []
            if l != -math.inf:
                tmp.append("X[{Y}] - X[{X}] >= {l}".format(Y=NameMap[Y],X=NameMap[X],l=l))
            if u != math.inf:
                tmp.append("X[{Y}] - X[{X}] <= {u}".format(Y=NameMap[Y],X=NameMap[X],u=u))
            mzn.write(" /\ ".join(tmp))
            if D > 1:
                mzn.write(" endif".format(i))
            mzn.write(";\n")
        if D > 1:
            mzn.write("constraint count(j in 1..{})(s{}[j] = true) {} 1;\n".format(D,i, "=" if tcsp else ">="))
           
    mzn.write("output[\"(sat)\"];\n")
    mzn.write("solve satisfy;")

    return mzn.getvalue()

def MiniZincHoleEncoder(TimePoints, Constraints, H):

    assert IsTCSP(Constraints)
    mzn = StringIO()
    NameMap = dict()
    
    for X in TimePoints:
        NameMap[X] = len(NameMap)+1

    mzn.write("array[1..{}] of var 0..{}: X;\n".format(len(NameMap), H))

    for i in range(0,len(Constraints)):
        (Y,X,l,u) = Constraints[i][0]
        assert l != -math.inf or u != math.inf
        tmp = []
        if l != -math.inf:
            tmp.append("X[{Y}] - X[{X}] >= {l}".format(Y=NameMap[Y],X=NameMap[X],l=l))
        (Y,X,l,u) = Constraints[i][-1]
        if u != math.inf:
            tmp.append("X[{Y}] - X[{X}] <= {u}".format(Y=NameMap[Y],X=NameMap[X],u=u))

        if any(tmp):
            mzn.write("constraint {};\n".format(" /\ ".join(tmp)))

        for j in range(0,len(Constraints[i])-1):
            uj        = Constraints[i][j][3]
            ljplusone = Constraints[i][j+1][2]
            assert uj != math.inf and ljplusone != -math.inf
            mzn.write("constraint X[{Y}] - X[{X}] <= {uj} \/ X[{Y}] - X[{X}] >= {ljplusone};\n".format(Y=NameMap[Y],X=NameMap[X],uj=uj,ljplusone=ljplusone))

    mzn.write("output[\"(sat)\"];\n")
    mzn.write("solve satisfy;")
    return mzn.getvalue()

def SmtNaiveEncoder(TimePoints, Constraints, H):
    smtlib = StringIO()
    smtlib.write("(set-option :print-success false)\n(set-logic QF_RDL)\n")
    smtlib.write("\n".join("(declare-fun {} () Real)".format(X) for X in TimePoints))

    for i in range(0,len(Constraints)):
        smtlib.write("\n(assert")
        if len(Constraints[i]) > 1:
            smtlib.write(" (or")
        for j in range(0,len(Constraints[i])):
            (Y,X,l,u) = Constraints[i][j]
            if l != -math.inf and u != math.inf:
                smtlib.write(" (and")
            if l != -math.inf:
                if l < 0:
                    smtlib.write(" (>= (- {} {}) (- {}))".format(Y, X, abs(l)))
                else:
                    smtlib.write(" (>= (- {} {}) {})".format(Y, X, l))
            if u != math.inf:
                if u < 0:
                    smtlib.write(" (<= (- {} {}) (- {}))".format(Y, X, abs(u)))
                else:
                    smtlib.write(" (<= (- {} {}) {})".format(Y, X, u))
            if l != -math.inf and u != math.inf:
                smtlib.write(")")
        if len(Constraints[i]) > 1:
            smtlib.write(")")
        smtlib.write(")\n")

    smtlib.write("(check-sat)\n(exit)")

    return smtlib.getvalue()

def SmtSwitchEncoder(TimePoints, Constraints, H, tcsp=False):

    if tcsp:
        assert IsTCSP(Constraints)

    smtlib = StringIO()
    smtlib.write("(set-option :print-success false)\n(set-logic QF_RDL)\n")
    smtlib.write("\n".join("(declare-fun {} () Real)".format(X) for X in TimePoints))
    smtlib.write("\n")

    for i in range(0,len(Constraints)):
        if len(Constraints[i]) > 1:
            smtlib.write("\n".join("(declare-fun s{}_{} () Bool)".format(i,j) for j in range(0,len(Constraints[i]))))
            smtlib.write("\n")

    for i in range(0,len(Constraints)):
        disjunctive = (len(Constraints[i]) > 1)
        for j in range(0,len(Constraints[i])):
            (Y,X,l,u) = Constraints[i][j]
            if l != -math.inf:
                smtlib.write("(assert")
                if disjunctive:
                    smtlib.write(" (or (not s{}_{})".format(i,j))
                if l < 0:
                    smtlib.write(" (>= (- {} {}) (- {}))".format(Y, X, abs(l)))
                else:
                    smtlib.write(" (>= (- {} {}) {})".format(Y, X, l))
                if disjunctive:
                    smtlib.write(")")
                smtlib.write(")\n")
            if u != math.inf:
                smtlib.write("(assert")
                if disjunctive:
                    smtlib.write(" (or (not s{}_{})".format(i,j))
                if u < 0:
                    smtlib.write(" (<= (- {} {}) (- {}))".format(Y, X, abs(u)))
                else:
                    smtlib.write(" (<= (- {} {}) {})".format(Y, X, u))
                if disjunctive:
                    smtlib.write(")")
                smtlib.write(")\n")
        if disjunctive:
            smtlib.write("(assert (or ")
            smtlib.write(" ".join("s{}_{}".format(i,j) for j in range(0,len(Constraints[i]))))
            smtlib.write("))\n")

            if tcsp:
                for j1 in range(0,len(Constraints[i])):
                    for j2 in range(j1+1,len(Constraints[i])):
                        smtlib.write("(assert (or (not s{}_{}) (not s{}_{})))\n".format(i,j1,i,j2))

    smtlib.write("(check-sat)\n(exit)")

    return smtlib.getvalue()


def SmtHoleEncoder(TimePoints, Constraints, H):

    assert IsTCSP(Constraints)
    smtlib = StringIO()
    smtlib.write("(set-option :print-success false)\n(set-logic QF_RDL)\n")
    smtlib.write("\n".join("(declare-fun {} () Real)".format(X) for X in TimePoints) + "\n")

    for i in range(0,len(Constraints)):
        (Y,X,l1)  = Constraints[i][0][:3]
        uk = Constraints[i][-1][3]

        left = None
        if l1 != -math.inf:
            if l1 < 0:
                left = "(>= (- {} {}) (- {}))".format(Y,X,abs(l1))
            else:
                left = "(>= (- {} {}) {})".format(Y,X,l1)

        right = None
        if uk != math.inf:
            if uk < 0:
                right = "(<= (- {} {}) (- {}))".format(Y,X,abs(uk))
            else:
                right = "(<= (- {} {}) {})".format(Y,X,uk)

        if left != None:
            smtlib.write("(assert {})\n".format(left))
        if right != None:
            smtlib.write("(assert {})\n".format(right))

        for j in range(0,len(Constraints[i])-1):
            uj        = Constraints[i][j][3]
            ljplusone = Constraints[i][j+1][2]

            assert abs(uj) != math.inf and abs(ljplusone) != math.inf

            if uj < 0:
                uj_smt = "(<= (- {} {}) (- {}))".format(Y,X,abs(uj))
            else:
                uj_smt = "(<= (- {} {}) {})".format(Y,X,uj)

            if ljplusone < 0:
                ljplusone_smt = "(>= (- {} {}) (- {}))".format(Y,X,abs(ljplusone))
            else:
                ljplusone_smt = "(>= (- {} {}) {})".format(Y,X,ljplusone)

            smtlib.write("(assert (or {} {}))\n".format(uj_smt, ljplusone_smt))

    smtlib.write("(check-sat)\n(exit)")

    return smtlib.getvalue()


def MilpSwitchEncoder(TimePoints, Constraints, H, tcsp=False):

    if tcsp:
        assert IsTCSP(Constraints)

    switch_vars = set()
    LP = StringIO()
    LP.write("Minimize\n0 __unused_var__\nSubject To\n")
    for i in range(0,len(Constraints)):
        # Non disjunctive case: do not create switch variables
        D = len(Constraints[i])
        if D == 1:
            (Y,X,l,u) = Constraints[i][0]
            assert Y != X # mainly for cbc
            assert l != -math.inf or u != math.inf
            if l != -math.inf:
                LP.write("L{},0: {} - {} >= {}\n".format(i,Y,X,l))
            if u != math.inf:
                LP.write("U{},0: {} - {} <= {}\n".format(i,Y,X,u))
        # Disjunctive case: create switch variables
        else:
            if tcsp:
                (Y,X,l,u) = Constraints[i][0]
                left = l if l != -math.inf else -H
                (Y,X,l,u) = Constraints[i][-1]
                right = u if u != math.inf else H
            else:
                left = -H
                right = H

            for j in range(0,D):
                (Y,X,l,u) = Constraints[i][j]
                assert Y != X # mainly for cbc
                assert l != -math.inf or u != math.inf
                if l != -math.inf:
                    coeff = left-l
                    coeff = "- {}".format(abs(coeff)) if coeff < 0 else "+ {}".format(coeff)
                    LP.write("L{},{}: {} - {} {} s{},{} >= {}\n".format(i,j,Y,X,coeff,i,j,left))
                    switch_vars.add("s{},{}".format(i,j))
                if u != math.inf:
                    coeff = right-u
                    coeff = "- {}".format(abs(coeff)) if coeff < 0 else "+ {}".format(coeff)
                    LP.write("U{},{}: {} - {} {} s{},{} <= {}\n".format(i,j,Y,X,coeff,i,j,right))
                    switch_vars.add("s{},{}".format(i,j))
            LP.write("sum{}: ".format(i))
            LP.write(" + ".join("s{},{}".format(i,j) for j in range(0,len(Constraints[i]))))
            if tcsp:
                LP.write(" = 1\n")
            else:
                LP.write(" >= 1\n")

    LP.write("Bounds\n")
    LP.write("Binaries\n")
    LP.write(" ".join(switch_vars))
    LP.write("\nEnd")
    return LP.getvalue()

# Warning! READ BEFORE USE.
# This function assumes the following.
# All variables but one (Z) have domain [minD,maxD]. Z is fixed at zero.
# The first set of constraints is:
# X - Z \in [minD,maxD].
#
# This function detects automatically Z, minD, maxD from the first listed constraint (i.e., Constraints[0][0]).
# If the .tn file lists the constraints differently the behavior of this method is undefined.
def MilpSwitchEncoderBoundedDomains(TimePoints, Constraints, tcsp=False):
    assert len(Constraints) > 0
    (X, Z, minD, maxD) = Constraints[0][0]
    switch_vars = set()
    LP = StringIO()
    LP.write("Minimize\n0 __unused_var__\nSubject To\n")
    LP.write("Z: {} = 0\n".format(Z))
    for i in range(0,len(Constraints)):
        # Non disjunctive case: do not create switch variables
        D = len(Constraints[i])
        if D == 1:
            (Y,X,l,u) = Constraints[i][0]
            assert Y != X # mainly for cbc
            assert l != -math.inf or u != math.inf
            if l != -math.inf:
                LP.write("L{},0: {} - {} >= {}\n".format(i,Y,X,l))
            if u != math.inf:
                LP.write("U{},0: {} - {} <= {}\n".format(i,Y,X,u))
        # Disjunctive case: create switch variables
        else:
            left  = minD - maxD
            right = maxD - minD

            for j in range(0,D):
                (Y,X,l,u) = Constraints[i][j]
                assert Y != X # mainly for cbc
                assert l != -math.inf or u != math.inf
                if l != -math.inf:
                    coeff = left-l
                    coeff = "- {}".format(abs(coeff)) if coeff < 0 else "+ {}".format(coeff)
                    LP.write("L{},{}: {} - {} {} s{},{} >= {}\n".format(i,j,Y,X,coeff,i,j,left))
                    switch_vars.add("s{},{}".format(i,j))
                if u != math.inf:
                    coeff = right-u
                    coeff = "- {}".format(abs(coeff)) if coeff < 0 else "+ {}".format(coeff)
                    LP.write("U{},{}: {} - {} {} s{},{} <= {}\n".format(i,j,Y,X,coeff,i,j,right))
                    switch_vars.add("s{},{}".format(i,j))
            LP.write("sum{}: ".format(i))
            LP.write(" + ".join("s{},{}".format(i,j) for j in range(0,len(Constraints[i]))))
            if tcsp:
                LP.write(" = 1\n")
            else:
                LP.write(" >= 1\n")

    LP.write("Bounds\n")
    LP.write("Binaries\n")
    LP.write(" ".join(switch_vars))
    LP.write("\nEnd")
    return LP.getvalue()

def MilpHoleEncoder(TimePoints, Constraints, H, holeCuts=False):

    assert IsTCSP(Constraints)

    hole_vars = set()
    LP = StringIO()
    LP.write("Minimize\n0 __unused_var__\nSubject To\n")
    for i in range(0,len(Constraints)):
        # Non disjunctive case
        D = len(Constraints[i])
        if D == 1:
            (Y,X,l,u) = Constraints[i][0]
            assert Y != X # mainly for cbc
            assert l != -math.inf or u != math.inf
            if l != -math.inf:
                LP.write("L{},0: {} - {} >= {}\n".format(i,Y,X,l))
            if u != math.inf:
                LP.write("U{},0: {} - {} <= {}\n".format(i,Y,X,u))
        # Disjunctive case
        else:
            (Y,X,l,u) = Constraints[i][0]
            left = l if l != -math.inf else -H
            (Y,X,l,u) = Constraints[i][-1]
            right = u if u != math.inf else H

            for j in range(0,D-1):
                hole = "h{}_{}".format(i,j)
                hole_vars.add(hole)
                (Y,X,l_j,u_j) = Constraints[i][j]
                (Y,X,l_jplus1,u_jplus1) = Constraints[i][j+1]
                coeff = left - l_jplus1
                coeff = "- {}".format(abs(coeff)) if coeff < 0 else "+ {}".format(coeff)
                LP.write("L{},{}: {} - {} {} {} >= {}\n".format(i,j,Y,X,coeff,hole,left))

                coeff = u_j - right
                coeff = "- {}".format(abs(coeff)) if coeff < 0 else "+ {}".format(coeff)
                LP.write("U{},{}: {} - {} {} {} <= {}\n".format(i,j,Y,X,coeff,hole,u_j))

                if holeCuts:
                    # h_{i,j} >= h_{i,j+1}
                    if j < D-2:
                        next_hole = "h{}_{}".format(i,j+1)
                        LP.write("H{},{}: {} - {} >= 0\n".format(i,j,hole,next_hole))


    LP.write("Bounds\n")
    LP.write("Binaries\n")
    LP.write(" ".join(hole_vars))
    LP.write("\nEnd")
    return LP.getvalue()


def SolveSMT(instance, encoder, solver, timeout=None, debug=False):

    start = time.time()
    TimePoints, Constraints, H = LoadDtp(instance)

    if encoder.startswith("naive"):
        smtlib = SmtNaiveEncoder(TimePoints, Constraints, H)
    elif encoder.startswith("switch") and not encoder.startswith("switch-tcsp"):
        smtlib = SmtSwitchEncoder(TimePoints, Constraints, H)
    elif encoder.startswith("switch-tcsp"):
        smtlib = SmtSwitchEncoder(TimePoints, Constraints, H, tcsp=True)
    elif encoder.startswith("hole"):
        smtlib = SmtHoleEncoder(TimePoints, Constraints, H)
    end = time.time()
    encoding_time = end - start

    if debug:
        with open("{}/__{}__.smt2".format(TmpDir, os.path.basename(instance)), "w") as f:
            f.write(smtlib)

    start = time.time()
    try:
        p = subprocess.run(shlex.split(Solvers["smt"][solver]["cmd"]), input=smtlib.encode(), stdout=subprocess.PIPE, timeout=timeout)
        if p.returncode != 0:
            answer = "E"
        else:
            answer = int(Solvers["smt"][solver]["out"] == p.stdout.decode().strip())

    except subprocess.CalledProcessError as e:
        print(f"{e}")
        answer = "E"
    except:
        answer = "?"

    end = time.time()
    solving_time = end - start

    return answer, encoding_time, solving_time

def SolveMILP(instance, encoder, solver, timeout=None, debug=False):
    lp_file = "{}/__{}__.lp".format(TmpDir, os.path.basename(instance))
    if os.path.exists(lp_file):
        os.remove(lp_file)

    start = time.time()
    TimePoints, Constraints, H = LoadDtp(instance)

    FeasTol = 1/H
    for i in range(6,10):
        if (1/(10**i)) < FeasTol:
            FeasTol = "1e-0{}".format(i)
            break
    #print("using: {}".format(FeasTol))
    if encoder == "switch":
        LP = MilpSwitchEncoder(TimePoints, Constraints, H)
    
    elif encoder == "switch-bd":
        LP = MilpSwitchEncoderBoundedDomains(TimePoints, Constraints)
    
    elif encoder == "switch-tcsp":
        LP = MilpSwitchEncoder(TimePoints, Constraints, H, tcsp=True)
    
    elif encoder == "switch-tcsp-bd":
        LP = MilpSwitchEncoderBoundedDomains(TimePoints, Constraints, tcsp=True)
    
    elif encoder == "hole":
        LP = MilpHoleEncoder(TimePoints, Constraints, H)
    
    elif encoder == "hole-hc":
        LP = MilpHoleEncoder(TimePoints, Constraints, H, holeCuts=True)

    with open(lp_file, "w") as f:
        f.write(LP)
    end = time.time()
    encoding_time = end - start

    start = time.time()
    try:
        #print(Solvers["milp"][solver]["cmd"].format(input_file=lp_file, feas_tol=FeasTol))
        p = subprocess.run(shlex.split(Solvers["milp"][solver]["cmd"].format(input_file=lp_file, feas_tol=FeasTol)), stdout=subprocess.PIPE, timeout=timeout)
        #print(p.stdout)
        if p.returncode != 0:
            answer = "E"
        else:
            answer = int(Solvers["milp"][solver]["out"] in p.stdout.decode().strip())
    except subprocess.CalledProcessError as e:
        print(f"{e}")
        answer = "E"
    except subprocess.TimeoutExpired as e:
        answer = "?"
    end = time.time()
    solving_time = end - start
    if not debug:
        os.remove(lp_file)

    return answer, encoding_time, solving_time

def SolveSAT(instance, encoder, solver, timeout=None, debug=False):
    if encoder == "tcsp":
        encoder = SatModelMethod.EXONE 
    elif encoder == "hole":
        encoder = SatModelMethod.HOLES
    else:
        encoder = SatModelMethod.STANDARD

    start = time.time()
    dimacs = SatModel(open(instance, "r").read(), encoder)
    end = time.time()
    encoding_time = end - start

    if debug:
        with open("{}/__{}__.cnf".format(TmpDir, os.path.basename(instance)) , "w") as f:
            f.write(dimacs)

    start = time.time()
    try:
        p = subprocess.run(shlex.split(Solvers["sat"][solver]["cmd"]), input=dimacs.encode(), stdout=subprocess.PIPE, timeout=timeout)
        
        if p.returncode not in {10,20}:
            answer = "E"
        else:
            #answer = int(Solvers["sat"][solver]["out"] in p.stdout.decode().strip())
            answer = int(p.returncode == 10)
    except subprocess.CalledProcessError as e:
        print(f"{e}")
        answer = "E"
    except subprocess.TimeoutExpired as e:
        answer = "?"
    
    end = time.time()
    solving_time = end - start

    return answer, encoding_time, solving_time

def SolveCP(instance, encoder, solver, timeout=None, debug=False):
    start = time.time()
    TimePoints, Constraints, H = LoadDtp(instance)

    mzn = None
    if encoder.startswith("naive"):
        mzn = MiniZincNaiveEncoder(TimePoints, Constraints, H)
    elif encoder.startswith("switch") and not encoder.startswith("switch-tcsp"):
        mzn = MiniZincSwitchEncoder(TimePoints, Constraints, H)
    elif encoder.startswith("switch-tcsp"):
        mzn = MiniZincSwitchEncoder(TimePoints, Constraints, H, tcsp=True)
    elif encoder.startswith("hole"):
        mzn = MiniZincHoleEncoder(TimePoints, Constraints, H)

    end = time.time()
    encoding_time = end - start

    if debug:
        with open("{}/__{}__.mzn".format(TmpDir, os.path.basename(instance)) , "w") as f:
            f.write(mzn)

    start = time.time()
    try:
        p = subprocess.run(shlex.split(Solvers["cp"][solver]["cmd"]), input=mzn.encode(), stdout=subprocess.PIPE, timeout=timeout)
        if p.returncode != 0:
            answer = "E"
        else:
            answer = int(Solvers["cp"][solver]["out"] in p.stdout.decode().strip())
    except subprocess.CalledProcessError as e:
        print(f"{e}")
        answer = "E"
        subprocess.run(shlex.split("killall -9 fzn-{}".format(solver)))
    except subprocess.TimeoutExpired as e:
        answer = "?"
        subprocess.run(shlex.split("killall -9 fzn-{}".format(solver)))
    end = time.time()
    solving_time = end - start

    return answer, encoding_time, solving_time

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("instance", help="benchmarks directory")
    parser.add_argument("encoder",  help=", ".join(Encoders.keys()))
    parser.add_argument("solver",   help=", ".join([s for f in Solvers.keys() for s in Solvers[f]]))
    parser.add_argument("-t", "--timeout", type=int, help="timeout in seconds (default none)")
    parser.add_argument("-d", "--debug", help="dump encoded problem to file", action="store_true", default=False)
    args = parser.parse_args()

    if not os.path.exists(TmpDir):
        os.mkdir(TmpDir)

    assert args.encoder in Encoders
    assert args.solver in {s for f in Solvers.keys() for s in Solvers[f]}

    if "smt-" in args.encoder:
        assert args.solver in Solvers["smt"].keys()

    if "sat" in args.encoder:
        assert args.solver in Solvers["sat"].keys()

    if "milp-" in args.encoder:
        assert args.solver in Solvers["milp"].keys()

    if "cp-" in args.encoder:
        assert args.solver in Solvers["cp"].keys()

    framework = detect_framework(args.encoder)

    if framework == "smt":
        answer, encoding_time, solving_time = SolveSMT(args.instance, args.encoder[4:], args.solver, timeout=args.timeout, debug=args.debug)
    elif framework == "milp":
        answer, encoding_time, solving_time = SolveMILP(args.instance, args.encoder[5:], args.solver, timeout=args.timeout, debug=args.debug)
    elif framework == "sat":
        answer, encoding_time, solving_time = SolveSAT(args.instance, args.encoder[4:], args.solver, timeout=args.timeout, debug=args.debug)
    elif framework == "cp":
        answer, encoding_time, solving_time = SolveCP(args.instance, args.encoder[3:], args.solver, timeout=args.timeout, debug=args.debug)
    else:
        assert False

    if answer == 1:
        print("Consistent")
    elif answer == 0:
        print("Inconsistent")
    elif answer == "?":
        print("Timeout")
    else:
        assert answer == "E"
        print("Error")
    print("Encoding time: {} seconds".format(encoding_time))
    print("Solving time: {} seconds".format(solving_time))
