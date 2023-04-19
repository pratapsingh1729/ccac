from config import ModelConfig
from model import make_solver
from z3 import And, ArithRef, If, Implies, Not, Or
from abr import make_abr_periodic
from cache import run_query
from plot import plot_model
from utils import make_periodic


def bb_abr_buffering_query(T, buffering_timesteps):
    c = ModelConfig(N=1,
                    D=1,
                    R=1,
                    T=T,
                    C=1,
                    buf_min=None,
                    buf_max=None,
                    dupacks=None,
                    cca="aimd",
                    compose=True,
                    alpha=None,
                    pacing=False,
                    epsilon="zero",
                    unsat_core=False,
                    simplify=False,
                    app="bb_abr")

    s, v = make_solver(c)
    dur = 1
    # Consider the no loss case for simplicity
    s.add(v.L[0] == 0)
    # s.add(v.alpha < 2)
    # Lowest bitrate is lower than link rate
    s.add(v.av[0].Ch_s[0] / c.C + c.D <= v.av[0].chunk_time)
    # A chunk is at-least 2 RTTs
    s.add(v.av[0].chunk_time >= 2 * c.R)

    # We'll let the algorithm "cheat" and know the link rate so the slope it
    # picks is not too sleep
    for i in range(1, c.ac[0].N_c):
        pass
        s.add(v.av[0].Ch_t[i] > c.D +
              v.av[0].Ch_s[i] * (1 + c.ac[0].chunk_margin) / c.C)

    # Network is nice
    for t in range(1, c.T):
        pass
        # s.add(v.S_f[0][t] - v.S_f[0][t-1] == c.C)
        # s.add(v.A_f[0][t] == v.av[0].snd[t])

    # Network does not waste
    # s.add(v.W[0] == v.W[-1])

    # Link has enough capacity to handle the lowest bit-rate
    s.add(v.av[0].Ch_s[0] < c.C * v.av[0].chunk_time)

    # There is a stall
    # s.add(v.av[0].b[c.T//2-1] < 1)
    # s.add(v.av[0].b[c.T//2] == 0)

    conds = []
    for t in range(c.T - buffering_timesteps):
        ands = []
        for i in range(t, t + buffering_timesteps):
            ands.append(v.av[0].b[i] == 0)
        conds.append(And(*ands))
    s.add(Or(*conds))


    make_abr_periodic(c.ac[0], v.av[0], c, s, v)
    make_periodic(c, s, v, dur)
    qres = run_query(s, c, timeout=120)
    print("{:>7.7}".format(qres.satisfiable), end=" ")
    # if str(qres.satisfiable) == "sat":
    #     plot_model(qres.model, c)

if __name__ == "__main__":
    print("buftime", end=" ")
    Trange = range(6, 25)
    for T in Trange:
        print("   T={:>2}".format(T), end = " ")
    print("")
    for buffering_timesteps in [1,2,3,4,5]:
        print("{:^7}".format(buffering_timesteps), end = " ")
        for T in Trange:
            bb_abr_buffering_query(T, buffering_timesteps)
        print("")