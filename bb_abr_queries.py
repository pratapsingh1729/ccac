from z3 import And, Not, Or
from abr import App
from config import ModelConfig
from model import make_solver
from my_solver import MySolver
from variables import Variables
from plot import plot_model





def run_abr_query(cca, abr, utilization_threshold):
    from cache import run_query
    from utils import make_periodic

    c = ModelConfig(N=1,
                    D=1,
                    R=1,
                    T=10,
                    C=1,
                    buf_min=2,
                    buf_max=None, # infinity
                    dupacks=None,
                    cca=cca, # only rocc and aimd are good in the compose=true model, copa in compose=false
                    compose=False, # whether the model admits multiple network elements (composition property)
                    alpha=None,
                    pacing=False,
                    epsilon="zero",
                    unsat_core=False,
                    simplify=False,
                    app=abr)

    # for AIMD dur=1, for Copa dur=c.R+c.D, for BBR dur=2*c.R

    # start_T = None
    dur = None
    if cca=="aimd":
        dur = 1
    elif cca=="rocc":
        dur = 4
    elif cca=="copa":
        dur = c.R+c.D
    elif cca=="bbr":
        dur = 2*c.R
    else:
        print("Unrecognized CCA")
        return None

    # Query: Low throughput and low cwnd
    s, v = make_solver(c)
    # dur = v.cv.dur
    # s.add(v.alpha < 2)

    # Require a small alpha (i.e. a high link rate in terms of MSS/timestep)
    s.add(v.alpha <= 0.25 * c.C * c.R)
    # s.add(v.L[0] == 0)

    # s.add(v.A_f[0][0] == v.c_f[0][0]) 

    # We don't want an example with timeouts
    for t in range(c.T):
        s.add(Not(v.timeout_f[0][t]))

    # conds = []
    # for t in range(0, c.T - 1):
    #     conds.append(And(
    #             # Cwnd is decreasing in this iteration
    #             v.c_f[0][t+1] < v.c_f[0][t],
    #             # Service in this timestep is low
    #             # v.S[t+1] - v.S[t] <= utilization_threshold * c.C
    #         ))
    # s.add(Or(*conds))
    s.add(v.S[-1] - v.S[0] < utilization_threshold * c.C * (c.T - 0))

    make_periodic(c,s,v,dur)

    qres = run_query(s, c, timeout=1200)
    return qres, c


if __name__ == "__main__":
    # for utilization_threshold in [0.1, 0.25, 0.5, 0.6]:
    #     print(f"\n\n\nutilization_threshold = {utilization_threshold}\n")
    #     for cca in ["aimd", "rocc", "copa", "bbr"]:
    #         for abr in ["bulk", "bb_abr"]:
    #             print(f"cca = {cca}, abr = {abr}")
    #             result, _ = run_abr_query(cca, abr, utilization_threshold)
    #             if result is None:
    #                 print("\t\terror\n")
    #             else:
    #                 print(f"\t\t{result.satisfiable}")
    for utilization_threshold in [0.1]:
        print(f"\n\n\nutilization_threshold = {utilization_threshold}\n")
        for cca in ["aimd"]:
            for abr in ["bulk", "bb_abr"]:
                print(f"cca = {cca}, abr = {abr}")
                result, c = run_abr_query(cca, abr, utilization_threshold)
                if result is None:
                    print("\t\terror\n")
                else:
                    print(f"\t\t{result.satisfiable}")        
                    if str(result.satisfiable) == "sat":
                        plot_model(result.model, c)
