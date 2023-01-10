TmpDir         = "__tmp__"
StatsDir       = "stats"
MetricsDir     = "metrics"
SolvingTimeDir = "solving_time"
LegendsDir     = "legends"
ModelTimeDir   = "encoding_time"

Encoders = dict()

Encoders["smt-naive"]                  = {"marker" : "o", "linestyle" : "-"  }
Encoders["smt-switch"]                 = {"marker" : "^", "linestyle" : "-"  }
Encoders["smt-switch-tcsp"]            = {"marker" : "*", "linestyle" : "-"  }
Encoders["smt-hole"]                   = {"marker" : "p", "linestyle" : "-"  }

Encoders["milp-switch"]                = {"marker" : "s", "linestyle" : "-"  }
Encoders["milp-switch-bd"]             = {"marker" : "s", "linestyle" : "-"  }
Encoders["milp-switch-tcsp"]           = {"marker" : "d", "linestyle" : "-"  }
Encoders["milp-switch-tcsp-bd"]        = {"marker" : "d", "linestyle" : "-"  }
Encoders["milp-hole"]                  = {"marker" : "+", "linestyle" : "-"  }
Encoders["milp-hole-hc"]               = {"marker" : "+", "linestyle" : "-"  }

Encoders["sat-naive"]                  = {"marker" : "v", "linestyle" : "-"  }
Encoders["sat-xor"]                    = {"marker" : "P", "linestyle" : "-"  }
Encoders["sat-hole"]                   = {"marker" : "H", "linestyle" : "-"  }

Encoders["cp-naive"]                  = {"marker" : "<", "linestyle" : "-"  }
Encoders["cp-switch"]                 = {"marker" : "8", "linestyle" : "-"  }
Encoders["cp-switch-tcsp"]            = {"marker" : ">", "linestyle" : "-"  }
Encoders["cp-hole"]                   = {"marker" : "X", "linestyle" : "-"  }


Solvers  = {"smt"  : dict(), 
			"sat"  : dict(),
			"milp" : dict(),
			"cp"  : dict()}

Solvers["smt"]["yices"]   = {"cmd"   : "yices-smt2",
							 "out"   : "sat",
							 "color" : "#ffba08"}

Solvers["smt"]["z3"]      = {"cmd"   : "z3 -smt2 -in",
							 "out"   : "sat",
							 "color" : "#ba274a"}

Solvers["smt"]["mathsat"] = {"cmd"   : "mathsat -input=smt2",
							 "out"   : "sat",
							 "color" : "#fe6a86"}

Solvers["smt"]["cvc4"]    = {"cmd"   : "cvc4 --lang smt2",
							 "out"   : "sat",
							 "color" : "#0c44ac"}

Solvers["smt"]["veriT"]   = {"cmd"   : "veriT --input=smtlib2 --disable-banner",
							 "out"   : "sat",
							 "color" : "#8207c5"}

Solvers["smt"]["opensmt"] = {"cmd"   : "opensmt",
							 "out"   : "sat",
							 "color" : "#56494E"}

Solvers["sat"]["kissat"]  = {"cmd"   : "kissat -q -n",
							 "out"   : "s SATISFIABLE",
							 "color" : "#ee6352"}

Solvers["sat"]["cadical"] = {"cmd"   : "cadical -q -n",
							 "out"   : "s SATISFIABLE",
							 "color" : "#ae5147"}

Solvers["sat"]["cryptominisat"] = {"cmd" : "cryptominisat5 --verb 0 -s 0",
							 "out"   : "s SATISFIABLE",
							 "color" : "#909595"}

Solvers["milp"]["gurobi"] = {"cmd"   : "gurobi_cl MIPFocus=1 FeasibilityTol={feas_tol} IntFeasTol={feas_tol} {input_file}",
							 "out"   : "Solution count 1: 0",
							 "color" : "#27a300"}

Solvers["milp"]["cplex"]  = {"cmd"   : "cplex -c \"read {input_file}\" \"set simplex tolerances feasibility {feas_tol}\" \"set mip tolerances integrality {feas_tol}\" \"set mip pool capacity 1\" \"optimize\" \"quit\"",
							 "out"   : "Solution pool: 1 solution saved",
							 "color" : "#2191fb"}

Solvers["milp"]["scip"]   = {"cmd"   : "scip -c \"read {input_file}\" -c \"set numerics feastol {feas_tol}\" -c optimize -c quit",
							 "out"   : "problem is solved [optimal solution found]",
							 "color" : "#ec3f13"}

Solvers["milp"]["cbc"]    = {"cmd"   : "cbc {input_file} primalT={feas_tol} integerT={feas_tol} solve exit",
							 "out"   : "Result - Optimal solution found",
							 "color" : "#34073d"}

Solvers["cp"]["chuffed"] = {"cmd"   : "minizinc --solver Chuffed -",
						 	 "out"   : "(sat)",
							 "color" : "#023e8a"}

Solvers["cp"]["gecode"]  = {"cmd"   : "minizinc --solver Gecode -",
						 	 "out"   : "(sat)",
							 "color" : "#013e8a"}

Solvers["cp"]["or-tools"]  = {"cmd"   : "minizinc --solver OR-tools -",
						 	 "out"   : "(sat)",
							 "color" : "#013e8a"}


ModelColor = "#000000"
#ModelColor = "#f46036"

def detect_framework(encoder):
	framework = None
	if encoder[0:4] == "smt-":
		framework = "smt"
	elif encoder[0:5] == "milp-":
		framework = "milp"
	elif encoder[0:3] == "sat":
		framework = "sat"
	elif encoder[0:2] == "cp":
		framework = "cp"

	return framework
