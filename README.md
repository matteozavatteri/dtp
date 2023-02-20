# Welcome! This repository is a place containing information on efficient techniques to solve the Disjunctive Temporal Problem

## Benchmarks, encodings, and solving techniques are described in the following paper:

[1] Matteo Zavatteri, Alice Raffaele, Dario Ostuni, Romeo Rizzi. An Interdisciplinary Experimental Evaluation on the Disjunctive Temporal Problem. Constraints.

[Link to paper]()

    @article{ 
        author = {Zavatteri, Matteo and Raffaele, Alice and Ostuni, Dario and Rizzi, Romeo},
        title = {An Interdisciplinary Experimental Evaluation on the Disjunctive Temporal Problem},
    	year = {2023},
	    journal = {Constraints},
	    volume = {28},
	    number = {1},
	    pages = {1-12},
	    doi = {10.1007/s10601-023-09342-7},
	    type = {Letter}
    }


# Required tools

## MILP solvers: Gurobi, CPLEX, CBC, SCIP
     
## SMT solvers: Yices, z3, CVC4, veriT, MathSAT5, OpenSMT2

## SAT solvers: Kissat, CaDiCaL, CryptoMiniSAT

## CP solvers (Install the MiniZinc suite): Chuffed, Gecode, OR-tools (fzn interface to be configured)



## Python

* [Python3](https://www.python.org)
* [matplotlib](https://matplotlib.org)
* possibly some other dependencies, according to your specific OS configuration.


# Solving the instances
Download [FBK benchmarks](https://www.mikand.net/thesis/constraints2013.tar.bz2)</br>
Decompress all .tar.bz2

    $ mv constraints2013/benchmarks/tcsp cmr-2013-tcsp
    $ mv constraints2013/benchmarks/dtp cmr-2013-dtp
	$ mkdir __tmp__
	$ python Benchmark.py -h	

Example:

    $ python Benchmark.py industrial-1-dtp milp-switch gurobi -t 600
    
(see  "stats" folder for the json files)	

For single experiments, see 

    $ python dtp.py -h

Example:

    $ python dtp.py industrial-1-dtp/000 milp-switch gurobi -t 600


# Computing the graphics

	$ python Graphics.py dimacs-gc-tcsp
	$ python Graphics.py industrial-2-dtp
	$ python Graphics.py cmr-2013-dtp
	$ python Graphics.py fhcpcs-tcsp		
	$ python Graphics.py industrial-3-dtp
	$ python Graphics.py cmr-2013-tcsp
	$ python Graphics.py industrial-1-dtp
	$ python Graphics.py orrz-2021-dtp

(see  "solving_time/encoding_time" folders)

The SAT encoders were developed by [@dariost](https://github.com/dariost). 