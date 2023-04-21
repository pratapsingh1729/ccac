import argparse
from z3 import And, If, Implies, Or

from binary_search import BinarySearch, find_bound
from cache import run_query
from config import ModelConfig
from model import Variables, make_solver, min_send_quantum
from plot import plot_model


def prove_loss_bounds(timeout: float):
    '''Prove loss bounds for a particular buffer length. Need to sweep buffer
    sizes to get confidence that the bounds hold.

    '''
    c = ModelConfig.default()
    # You can prove the theorem for other values of buffer as well (note, BDP =
    # 1). For smaller buf_min (and buf_max where buf_min=buf_max), pick smaller
    # bounds on alpha (see explanation below). For larger buf_min, increase T
    c.buf_min = 1
    c.buf_max = 1
    c.cca = "aimd"

    def max_cwnd(v: Variables):
        return (c.C*(c.R + c.D) + c.buf_min + v.alpha)

    def max_undet(v: Variables):
        ''' We'll prove that the number of undetected losses will be below this
        at equilibrium

        '''
        return (c.C*(c.R + c.D) + v.alpha)

    # # If cwnd > max_cwnd and undetected <= max_undet, cwnd will decrease
    # c.T = 10
    # s, v = make_solver(c)
    # # Lemma's assumption
    # s.add(v.c_f[0][0] > max_cwnd(v))
    # s.add(v.L_f[0][0] - v.Ld_f[0][0] <= max_undet(v))
    # # We need to assume alpha is small, since otherwise we get uninteresting
    # # counter-examples. This assumption is added to the whole theorem.
    # s.add(v.alpha < (1 / 4) * c.C * c.R)
    # # Lemma's statement's converse
    # s.add(v.c_f[0][-1] >= v.c_f[0][0] - v.alpha)
    # print("Proving that if cwnd is too big and undetected is small enough, "
    #       "cwnd will decrease")
    # qres = run_query(s, c, timeout)
    # print(qres.satisfiable)
    # assert(qres.satisfiable == "unsat")

    # If undetected > max_undet, either undetected will fall by at least C
    # bytes (and cwnd won't exceed max_cwnd) or it might not if initial cwnd >
    # max_cwnd. In the latter case, cwnd would decrease by the end

    # Note: this lemma by itself proves that undetected will eventually fall
    # below max_undet. Then, coupled with the above lemma, we have that AIMD
    # will always enter steady state
    # s, v = make_solver(c)
    # # Lemma's assumption
    # min_send_quantum(c, s, v)
    # s.add(v.L_f[0][0] - v.Ld_f[0][0] > max_undet(v))
    # s.add(Or(
    #     v.L_f[0][-1] - v.Ld_f[0][-1] > v.L_f[0][0] - v.Ld_f[0][0] - c.C,
    #     v.c_f[0][-1] > max_cwnd(v)))
    # s.add(v.alpha < 1 / 5)
    # # Lemma's statement's converse
    # s.add(Or(v.c_f[0][0] <= max_cwnd(v),
    #          v.c_f[0][-1] >= v.c_f[0][0] - v.alpha))
    # print("Proving that undetected will decrease eventually")
    # qres = run_query(s, c, timeout)
    # print(qres.satisfiable)
    # assert(qres.satisfiable == "unsat")

    # If we are in steady state, we'll remain there. In steady state: cwnd <=
    # max_cwnd, undetected <= max_undet
    c.T = 12

    c.app = "bb_abr"

    s, v = make_solver(c)

    # Require chunk sizes to be comparable to BDP (smallest chunk size at least half the BDP, largest at least 1.5x the BDP)
    if c.app == "bb_abr":
        s.add(v.av[0].Ch_s[0] >= 0.5 * c.C * (c.R + c.D))
        s.add(v.av[0].Ch_s[-1] >= 1.5 * c.C * (c.R + c.D))

    # Lemma's assumption
    s.add(v.L_f[0][0] - v.Ld_f[0][0] <= max_undet(v))
    s.add(v.c_f[0][0] <= max_cwnd(v))
    s.add(v.alpha < 1 / 3)
    # Lemma's statement's converse
    s.add(Or(
        v.L_f[0][-3] - v.Ld_f[0][-3] > max_undet(v),
        # v.c_f[0][-3] > max_cwnd(v)
        ))
    print("Proving that if AIMD enters steady state, it will remain there")
    print(f"max_cwnd = {max_cwnd(v)}, max_undet = {max_undet(v)}")
    qres = run_query(s, c, timeout)
    print(qres.satisfiable)
    if (qres.satisfiable != "unsat"):
        plot_model(qres.model, c)


    # Prove that when app-limited, cwnd does not increase
    # c.T = 10

    # c.app = "bb_abr"

    # s, v = make_solver(c)

    # # Require chunk sizes to be comparable to BDP (smallest chunk size at least half the BDP, largest at least 1.5x the BDP)
    # if c.app == "bb_abr":
    #     s.add((v.av[0].Ch_s[0] + c.buf_min) / c.C + c.D <= v.av[0].chunk_time)
    #     for i in range(1, c.ac[0].N_c):
    #         # s.add(v.av[0].Ch_t[i] > c.D + ((v.av[0].Ch_s[i] + 5*c.buf_min) * (1 + c.ac[0].chunk_margin)) / c.C)
    #         s.add(v.av[0].Ch_t[i] > ((v.av[0].Ch_s[i])) / c.C)
    #     # s.add(v.av[0].Ch_s[0] >= 0.5 * c.C * (c.R + c.D))
    #     # s.add(v.av[0].Ch_s[-1] >= 1.5 * c.C * (c.R + c.D))

    # # Lemma's assumption
    # s.add(v.L_f[0][0] - v.Ld_f[0][0] <= max_undet(v))
    # s.add(v.c_f[0][0] <= max_cwnd(v))
    # s.add(v.alpha < 1 / 3)
    # for t in range(c.T):
    #     # App is rate-limiting the whole way through 
    #     s.add(v.A_f[0][t] >= v.av[0].snd[t])
    # # Lemma's statement's converse
    # s.add(
    #     v.c_f[0][-1] > v.c_f[0][3]
    #     )
    # print("Proving that when AIMD is app-limited, cwnd does not increase")
    # # print(f"max_cwnd = {max_cwnd(v)}, max_undet = {max_undet(v)}")
    # qres = run_query(s, c, timeout)
    # print(qres.satisfiable)
    # if (qres.satisfiable != "unsat"):
    #     plot_model(qres.model, c)


    # # Prove a theorem about when loss can happen using this steady state
    # c.T = 10
    # print("Proving threshold on when loss can happen")
    # for beta in [0.5, 1.9, 3]:
    #     c.buf_min = beta
    #     s, v = make_solver(c)
    #     # Lemma's assumption
    #     s.add(v.L_f[0][0] - v.Ld_f[0][0] <= max_undet(v))
    #     s.add(v.c_f[0][0] <= max_cwnd(v))
    #     s.add(v.alpha < 1 / 3)

    #     if beta <= c.C * (c.R + c.D):
    #         cwnd_thresh = c.buf_min - v.alpha
    #     else:
    #         cwnd_thresh = c.C * (c.R - 1) + c.buf_min - v.alpha

    #     for t in range(1, c.T):
    #         s.add(And(v.L_f[0][t] > v.L_f[0][t-1],
    #                   v.c_f[0][t-1] < cwnd_thresh))
    #     qres = run_query(s, c, timeout)
    #     print(qres.satisfiable)
    #     assert(qres.satisfiable == "unsat")


if __name__ == "__main__":
    prove_loss_bounds(600)
