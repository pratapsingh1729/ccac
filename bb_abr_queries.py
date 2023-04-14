from z3 import And, Not, Or
from abr import App
from config import ModelConfig
from model import make_solver
from my_solver import MySolver
from variables import Variables
from plot import plot_model



def run_abr_utilization_query(cca, abr, compose, utilization_threshold):
    from cache import run_query
    from utils import make_periodic

    c = ModelConfig(N=1,
                    D=1,
                    R=1,
                    T=10,
                    C=1,
                    buf_min=1,
                    buf_max=None, # infinity
                    dupacks=None,
                    cca=cca, # only rocc and aimd are good in the compose=true model, copa in compose=false
                    compose=compose, # whether the model admits multiple network elements (composition property)
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

    # Require a small alpha (i.e. a high link rate in terms of MSS/timestep)
    s.add(v.alpha <= 0.25 * c.C * c.R)
       
    s.add(v.A_f[0][0] == v.c_f[0][0]) 


    # Require chunk sizes to be comparable to link rate (smallest chunk size at least half the link rate, largest at least 1.5x the link rate)
    if abr=="bb_abr":
        s.add(v.av[0].Ch_s[0] >= max(0.5, utilization_threshold) * c.C)
        s.add(v.av[0].Ch_s[-1] >= 1.5 * c.C)


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
    s.add(v.S[-1] - v.S[0] < utilization_threshold * c.C * c.T)

    make_periodic(c,s,v,dur)

    qres = run_query(s, c, timeout=1200)
    return qres, c

def run_abr_buffering_query(cca, abr, compose, buffering_timesteps):
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
                    compose=compose, # whether the model admits multiple network elements (composition property)
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

    # Query: Buffering    
    s, v = make_solver(c)

    # Require a small alpha (i.e. a high link rate in terms of MSS/timestep)
    s.add(v.alpha <= 0.25 * c.C * c.R)
    # s.add(v.L[0] == 0)

    # We don't want an example with timeouts
    for t in range(c.T):
        s.add(Not(v.timeout_f[0][t]))

    conds = []
    for t in range(c.T - buffering_timesteps):
        ands = []
        for i in range(t, t + buffering_timesteps):
            ands.append(v.av[0].b[i] == 0)
        conds.append(And(*ands))
    s.add(Or(*conds))

    # don't include initial buffering
    s.add(v.av[0].b[0] != 0)

    make_periodic(c,s,v,dur)

    qres = run_query(s, c, timeout=1200)
    return qres, c


def run_util_queries(print_counterexample=False):
    for utilization_threshold in [0.1]: #, 0.25, 0.5, 0.6]:
        print(f"\n\n\nutilization_threshold = {utilization_threshold}\n")
        for cca in ["aimd"]:
            for abr in ["bulk", "bb_abr"]:
                compose = True
                print(f"cca = {cca},\tabr = {abr}\tcompose={compose}")
                result, c = run_abr_utilization_query(cca, abr, compose, utilization_threshold)
                if result is None:
                    print("\terror\n")
                else:
                    print(f"\t{result.satisfiable}")        
                    if print_counterexample and str(result.satisfiable) == "sat":
                        plot_model(result.model, c)
                        print("\n\n")

def run_buffering_queuries(print_counterexample=False):
    for buffering_timesteps in [2,3,4,5]:
        print(f"\n\nbuffering_timesteps = {buffering_timesteps}\n")
        for cca in ["aimd"]:
            for abr in ["bb_abr"]:
                compose = False
                print(f"cca = {cca},\tabr = {abr},\tcompose={compose}")
                result, c = run_abr_buffering_query(cca, abr, compose, buffering_timesteps)
                if result is None:
                    print("\terror\n")
                else:
                    print(f"\t{result.satisfiable}")
                    if print_counterexample and str(result.satisfiable) == "sat":
                        plot_model(result.model, c)
                        print("\n\n")

if __name__ == "__main__":
    run_util_queries(print_counterexample=True)