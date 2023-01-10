#!/usr/bin/env python3

import argparse
from conf import  *
from dtp import *
import json
import os

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("benchdir", help="benchmarks directory")
    parser.add_argument("encoder",  help=", ".join(Encoders.keys()))
    parser.add_argument("solver",   help=", ".join([s for f in Solvers.keys() for s in Solvers[f]]))
    parser.add_argument("-t", "--timeout", type=int, help="timeout in seconds (default none)")
    args = parser.parse_args()

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


    args.benchdir = args.benchdir.strip("/")

    if not os.path.exists(StatsDir):
        os.mkdir(StatsDir)

    stats = dict()


    StatsFile = "{}/{}-{}-{}.json".format(StatsDir, args.benchdir.replace("/","-"), args.encoder, args.solver)

    # for "resume" purposes
    if os.path.exists(StatsFile):
        with open(StatsFile , "r") as f:
            stats = json.load(f)
            assert stats.keys() <= set(os.listdir(args.benchdir))

    if not os.path.exists(TmpDir):
        os.mkdir(TmpDir)

    framework = detect_framework(args.encoder)

    # Exclude those already analyzed
    toAnalyze = set(os.listdir(args.benchdir)) - stats.keys()
    for instance in sorted(toAnalyze):
        tn_file = args.benchdir + "/" + instance

        if framework == "smt":
            answer, encoding_time, solving_time = SolveSMT(tn_file, args.encoder[4:], args.solver, timeout=args.timeout)
        elif framework == "milp":
            answer, encoding_time, solving_time = SolveMILP(tn_file, args.encoder[5:], args.solver, timeout=args.timeout)
        elif framework == "sat":
            answer, encoding_time, solving_time = SolveSAT(tn_file, args.encoder[3:], args.solver, timeout=args.timeout)
        elif framework == "cp":
            answer, encoding_time, solving_time = SolveCP(tn_file, args.encoder[3:], args.solver, timeout=args.timeout)
        else:
            assert False

        stats[instance] = { "answer" : answer,
                            "encoding_time" : encoding_time,
                            "solving_time" : solving_time
                        }
        # Update previous json (overwrite it)
        with open(StatsFile, 'w') as f:
            json.dump(stats, f, sort_keys=True, indent=4)
