from config import ModelConfig
from model import Variables, make_solver, min_send_quantum
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
                    buf_min=1,
                    buf_max=1,
                    dupacks=None,
                    cca="aimd_appsafe",
                    compose=True,
                    alpha=None,
                    pacing=False,
                    epsilon="zero",
                    unsat_core=False,
                    simplify=False,
                    app="bb_abr")

    s, v = make_solver(c)
    dur = 1

    # Require a small alpha (i.e. a high link rate in terms of MSS/timestep)
    s.add(v.alpha <= 0.25 * c.C * c.R)
    # Consider the no loss case for simplicity
    # s.add(v.L[0] == 0)
    # s.add(v.alpha < 2)
    # Lowest bitrate is lower than link rate
    s.add((v.av[0].Ch_s[0] + c.buf_min) / c.C + c.D <= v.av[0].chunk_time)
    # A chunk is at-least 2 RTTs
    s.add(v.av[0].chunk_time >= 2 * c.R)

    # We'll let the algorithm "cheat" and know the link rate so the slope it
    # picks is not too sleep
    for i in range(1, c.ac[0].N_c):
        # s.add(v.av[0].Ch_t[i] > c.D + ((v.av[0].Ch_s[i] + 5*c.buf_min) * (1 + c.ac[0].chunk_margin)) / c.C)
        s.add(v.av[0].Ch_t[i] > ((v.av[0].Ch_s[i])) / c.C)

    # We don't want an example with timeouts
    for t in range(c.T):
        s.add(Not(v.timeout_f[0][t]))

    # Network is nice
    # for t in range(1, c.T):
    #     pass
        # s.add(v.S_f[0][t] - v.S_f[0][t-1] == c.C)
        # s.add(v.A_f[0][t] == v.av[0].snd[t])

    # Network does not waste
    # s.add(v.W[0] == v.W[-1])

    # s.add(v.L_f[0][0] - v.Ld_f[0][0] <= max_undet(v))
    # s.add(v.c_f[0][0] <= max_cwnd(v))

    conds = []
    for t in range(c.T - buffering_timesteps):
        ands = []
        for i in range(t, t + buffering_timesteps):
            ands.append(v.av[0].b[i] == 0)
        conds.append(And(*ands))
    s.add(Or(*conds))


    make_abr_periodic(c.ac[0], v.av[0], c, s, v)
    make_periodic(c, s, v, dur)
    qres = run_query(s, c, timeout=600)
    print("{:>7.7}".format(qres.satisfiable), end=" ")
    if str(qres.satisfiable) == "sat":
        print("")
        plot_model(qres.model, c)

if __name__ == "__main__":
    print("buftime", end=" ")
    Trange = range(10,11)
    for T in Trange:
        print("   T={:>2}".format(T), end = " ")
    print("")
    for buffering_timesteps in [1]:
        print("{:^7}".format(buffering_timesteps), end = " ")
        for T in Trange:
            bb_abr_buffering_query(T, buffering_timesteps)
        print("")