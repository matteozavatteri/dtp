#!/usr/bin/env python3

import argparse
from conf import *
import json
import matplotlib.pyplot as plt
import os
from statistics import mean

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("benchdir", help="benchmarks directory")

    args = parser.parse_args()
    args.benchdir = args.benchdir.strip("/")

    if not os.path.exists(StatsDir):
        os.mkdir(StatsDir)

    stats = dict()
    
    for framework in Solvers:
        for solver in Solvers[framework]:
            for encoder in Encoders:
                json_file = "{}/{}-{}-{}.json".format(StatsDir, args.benchdir.replace("/","-"),encoder,solver)
                if os.path.exists(json_file):
                    if encoder not in stats.keys():
                        stats[encoder] = dict()
                    with open(json_file , "r") as f:
                        stats[encoder][solver] = json.load(f)    

    #print("{}".format(stats))
    assert len(stats) != 0

    Instances = set()

    # Assert solver answers
    Answer = dict()
    for encoder in stats:
        for solver in stats[encoder]:
            if len(Instances) == 0:
                Instances = stats[encoder][solver].keys()
            else:
                assert Instances == stats[encoder][solver].keys()
            for instance in stats[encoder][solver]:
                #print("{} {} {}".format(solver, instance,encoder))
                if stats[encoder][solver][instance]["answer"] in {0,1}:
                    if instance not in Answer:
                        Answer[instance] = stats[encoder][solver][instance]["answer"]
                    else:
                        assert Answer[instance] == stats[encoder][solver][instance]["answer"]
    
    mark_every = 1
    ncol = 3
    if args.benchdir in {"orrz-2021-dtp"}:
        mark_every = 15
        ncol = 4

    elif args.benchdir in {"industrial-1-dtp"}:
        mark_every = 15
        ncol = 4

    elif args.benchdir in {"industrial-2-dtp"}:
        mark_every = 150
        ncol = 4

    elif args.benchdir in {"industrial-3-dtp"}:
        mark_every = 200
        ncol = 4

    elif args.benchdir in {"cmr-2013-dtp", "cmr-2013-tcsp"}:
        mark_every = 150
        ncol = 4

    elif args.benchdir in {"dimacs-gc-tcsp"}:
        mark_every = 5
        ncol = 4
        

    # Solving time
    if not os.path.exists(SolvingTimeDir):
        os.mkdir(SolvingTimeDir)

    fig, axes = plt.subplots()
    axes.set_xlabel('N')
    axes.set_ylabel('Global time (s)') 
    x = [i for i in range(1,len(Instances)+1)]
    for encoder in sorted(stats):
        for solver in sorted(stats[encoder]):
            y = []
            Insts = sorted(stats[encoder][solver])
            y.append(stats[encoder][solver][Insts[0]]["solving_time"])
            for instance in Insts[1:]:
                solving_time = stats[encoder][solver][instance]["solving_time"]
                y.append(y[-1] + solving_time)
            framework = detect_framework(encoder)
            axes.plot(x, y, color=Solvers[framework][solver]["color"], linestyle=Encoders[encoder]["linestyle"], marker=Encoders[encoder]["marker"], markevery=mark_every, label="{} {}".format(encoder,solver))
    #axes.legend(loc='best', ncol=ncol, fontsize=14)
    #plt.title("{} (solving time)".format(args.benchdir.replace("/","-"))) 
    plt.yscale('log')
    plt.grid(True)
    plt.savefig("{}/{}-solving-time.pdf".format(SolvingTimeDir,args.benchdir.replace("/","-")), format="pdf")

    # Model generation time
    if not os.path.exists(ModelTimeDir):
        os.mkdir(ModelTimeDir)

    fig, axes = plt.subplots()
    axes.set_xlabel('N')
    axes.set_ylabel('Global time (s)') 
    x = [i for i in range(1,len(Instances)+1)]
    for encoder in stats:
        solver = sorted(stats[encoder].keys())[0] # take any
        y = []
        Insts = sorted(stats[encoder][solver])
        y.append(stats[encoder][solver][Insts[0]]["encoding_time"])
        for instance in Insts[1:]:
            encoding_time = stats[encoder][solver][instance]["encoding_time"]
            y.append(y[-1] + encoding_time)
        axes.plot(x, y, color=ModelColor, linestyle=Encoders[encoder]["linestyle"], marker=Encoders[encoder]["marker"], markevery=mark_every, label="{} - encoding".format(encoder))
    #axes.legend(loc='best', ncol=2, fontsize=14)
    #plt.title("Solving time for {}".format(args.benchdir.replace("/","-"))) 
    #plt.title("{} (encoding time)".format(args.benchdir.replace("/","-"))) 
    plt.yscale('log')
    plt.grid(True)
    plt.savefig("{}/{}-encoding-time.pdf".format(ModelTimeDir,args.benchdir.replace("/","-")), format="pdf")


    LaTex = "{}/{}-solving-time-latex.txt".format(SolvingTimeDir,args.benchdir.replace("/","-"))
    with open(LaTex, "w") as f:
        f.write("\\scalebox{0.6}{\\begin{tabular}{cccrrrrr}\n")
        f.write("\\hline\n")
        f.write("\\textbf{Technology} & \\textbf{Encoding} & \\textbf{Solver} & \\textbf{Y} & \\textbf{N} & \\textbf{T} & \\textbf{E} & \\textbf{A}\\\\\n")
        f.write("\\hline\n")
        # Global stats

        Frameworks = {detect_framework(e) for e in Encoders}
        InOrder = ["smt", "milp", "sat", "cp"]
        assert set(InOrder) == Frameworks
        number_of_experiments = 0
        for fw in InOrder:
            N = sum(1 for e in Encoders if detect_framework(e) == fw and e in stats)
            M = sum(1 for e in Solvers for s in Solvers[e] if e == fw)

            f.write("\\multirow{{{}}}{{*}}{{\\textbf{{{}}}}} ".format(N*M,fw.upper()))
            
            for e in stats:
                if fw == detect_framework(e):
                    short_encoder_name = e if "-" not in e else e[e.index("-")+1:]
                    f.write(" & \\multirow{{{}}}{{*}}{{{}}} ".format(M,short_encoder_name))
                    first = True
                    for s in stats[e]:
                        f.write("& ")
                        if not first:
                            f.write("& ")
                        first = False
                        Y = sum(1 for i in Instances if stats[e][s][i]["answer"] == 1)
                        N = sum(1 for i in Instances if stats[e][s][i]["answer"] == 0)
                        T = sum(1 for i in Instances if stats[e][s][i]["answer"] == "?")
                        E = sum(1 for i in Instances if stats[e][s][i]["answer"] == "E")
                        number_of_experiments += len(stats[e][s])
                        A = round(mean(stats[e][s][i]['solving_time'] for i in stats[e][s]),2)
                        TS = round(sum(stats[e][s][i]['solving_time'] for i in stats[e][s]),2)
                        print("{} {}: Y={}, N={}, ?={}, E={}, A={}, Tot={}".format(e, s, Y, N, T, E, A, TS))
                        f.write("{} & {} & {} & {} & {} & {} \\\\\n".format(s,Y,N,T,E,A))
                    f.write("\\cline{2-8}\n")
            f.write("\\hline\n")
        f.write("\\end{tabular}}\n")
    
    TotalSolvingTime = sum(stats[e][s][i]["solving_time"] for e in stats for s in stats[e] for i in stats[e][s])
    print("TotalSolvingTime (global) = {} seconds".format(TotalSolvingTime))
    print("Number of experiments = {}".format(number_of_experiments))

    #TotalEncodingTime = sum(stats[e][s][i]["encoding_time"] for e in stats for s in stats[e] for i in stats[e][s])
    
    TotalEncodingTime = []
    for f in ["smt", "milp", "sat", "cp"]:
        NE = len({e for e in Encoders if detect_framework(e) == f})
        NS = len(Solvers[f].keys())
        TotalEncodingTime.append(NE * NS * sum(stats[e][s][i]["encoding_time"] for e in stats for s in stats[e] for i in stats[e][s] if detect_framework(e) == f))
    
    print("TotalEncodingTime = {} seconds".format(sum(TotalEncodingTime)))

