from z3 import And, Not, Or
from abr import App
from config import ModelConfig
from model import make_solver
from my_solver import MySolver
from variables import Variables


if __name__ == "__main__":
    from cache import run_query
    from plot import plot_model
    from utils import make_periodic

    c = ModelConfig(N=1,
                    D=1,
                    R=1,
                    T=5,
                    C=1,
                    buf_min=2, # infinity
                    buf_max=None, # infinity
                    dupacks=None,
                    cca="aimd", # only rocc and aimd are good in the compose=true model, copa in compose=false
                    compose=True, # whether the model admits multiple network elements (composition property)
                    alpha=None,
                    pacing=False,
                    epsilon="zero",
                    unsat_core=False,
                    simplify=False,
                    app="bb_abr")

    s, v = make_solver(c)
    # dur = v.cv.dur
    # Consider the no loss case for simplicity
    # s.add(v.alpha < 2)
    s.add(v.alpha <= 0.1 * c.C * c.R)
    s.add(v.L[0] == 0)

    x = 2
    # Query: Low throughput
    if True:
        s.add(v.A_f[0][0] == v.c_f[0][0])
        s.add(v.c_f[0][-1] < v.c_f[0][x])
        s.add(v.S[-1] - v.S[x] <= 0.1 * c.C * (c.T - x))
        for t in range(c.T):
            s.add(Not(v.timeout_f[0][t]))

    # Query: Does dummy dominate?
    elif False:
        s.add(v.av[0].actually_sent[-1] - v.av[0].actually_sent[5] <= 0.8 * (v.A[-1] - v.A[5]))

    qres = run_query(s, c, timeout=1200)
    print(qres.satisfiable)
    if str(qres.satisfiable) == "sat":
        plot_model(qres.model, c)
