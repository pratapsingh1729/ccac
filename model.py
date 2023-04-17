from z3 import And, Sum, Implies, Or, Not, If

from abr import make_buffer_based_app
from cca_aimd import cca_aimd
from cca_bbr import cca_bbr
from cca_conv import cca_conv
from cca_copa import cca_copa
from cca_fair import cca_fair
from cca_rocc import cca_rocc
from config import ModelConfig
from my_solver import MySolver
from panteabr import make_panteabr_app
from variables import Variables


def monotone(c: ModelConfig, s: MySolver, v: Variables):
    for t in range(1, c.T):
        for n in range(c.N):
            s.add(v.A_f[n][t] >= v.A_f[n][t - 1])
            s.add(v.Ld_f[n][t] >= v.Ld_f[n][t - 1])
            s.add(v.S_f[n][t] >= v.S_f[n][t - 1])
            s.add(v.L_f[n][t] >= v.L_f[n][t - 1])

            s.add(
                v.A_f[n][t] - v.L_f[n][t] >= v.A_f[n][t - 1] - v.L_f[n][t - 1])
        s.add(v.W[t] >= v.W[t - 1])
        s.add(c.C * t - v.W[t] >= c.C * (t-1) - v.W[t-1])


def initial(c: ModelConfig, s: MySolver, v: Variables):
    for n in range(c.N):
        # Making these positive actually matters. What the hell is negative
        # rate or loss?
        s.add(v.c_f[n][0] > 0)
        s.add(v.r_f[n][0] > 0)
        s.add(v.L_f[n][0] >= 0)
        s.add(v.Ld_f[n][0] >= 0)

        # These are invariant to y-shift. However, it does make the results
        # easier to interpret if they start from 0
        s.add(v.S_f[n][0] == 0)


def relate_tot(c: ModelConfig, s: MySolver, v: Variables):
    ''' Relate total values to per-flow values '''
    for t in range(c.T):
        s.add(v.A[t] == Sum([v.A_f[n][t] for n in range(c.N)]))
        s.add(v.L[t] == Sum([v.L_f[n][t] for n in range(c.N)]))
        s.add(v.S[t] == Sum([v.S_f[n][t] for n in range(c.N)]))


def network(c: ModelConfig, s: MySolver, v: Variables):
    for t in range(c.T):
        for n in range(c.N):
            s.add(v.S_f[n][t] <= v.A_f[n][t] - v.L_f[n][t])

        s.add(v.S[t] <= c.C * t - v.W[t])
        if t >= c.D:
            s.add(c.C * (t - c.D) - v.W[t - c.D] <= v.S[t])
        else:
            # The constraint is the most slack when black line is steepest. So
            # we'll say there was no wastage when t < 0
            s.add(c.C * (t - c.D) - v.W[0] <= v.S[t])

        if c.compose:
            if t > 0:
                s.add(
                    Implies(v.W[t] > v.W[t - 1],
                            v.A[t] - v.L[t] <= c.C * t - v.W[t]))
        else:
            if t > 0:
                s.add(
                    Implies(v.W[t] > v.W[t - 1],
                            v.A[t] - v.L[t] <= v.S[t] + v.epsilon))

        if c.buf_min is not None:
            if t > 0:
                s.add(
                    Implies(
                        v.L[t] > v.L[t - 1], v.A[t] - v.L[t] >= c.C *
                        (t - 1) - v.W[t - 1] + c.buf_min))
        else:
            s.add(v.L[t] == v.L[0])

        # Enforce buf_max if given
        if c.buf_max is not None:
            s.add(v.A[t] - v.L[t] <= c.C * t - v.W[t] + c.buf_max)


def loss_detected(c: ModelConfig, s: MySolver, v: Variables):
    for n in range(c.N):
        for t in range(c.T):
            for dt in range(c.T):
                if t - c.R - dt < 0:
                    continue
                # Loss is detectable through dupacks
                detectable = v.A_f[n][t-c.R-dt] - v.L_f[n][t-c.R-dt]\
                    + v.dupacks <= v.S_f[n][t-c.R]

                s.add(
                    Implies(And(Not(v.timeout_f[n][t]), detectable),
                            v.Ld_f[n][t] >= v.L_f[n][t - c.R - dt]))
                s.add(
                    Implies(And(Not(v.timeout_f[n][t]), Not(detectable)),
                            v.Ld_f[n][t] <= v.L_f[n][t - c.R - dt]))

            # We implement an RTO scheme that magically triggers when S(t) ==
            # A(t) - L(t). While this is not implementable in reality, it is
            # still realistic. First, if a CCAC version of the CCA times out,
            # then a real implementation will also timeout. The timeout may
            # occur a different duration than in the real world. The user
            # should be mindful of this and not take the timeout duration
            # literally. Nevertheless, this difference has no bearing on
            # subsequent behavior.

            # This is also the only *legitimate* case where we want our CCA to
            # timeout. A CCAC adversary can cause a real implementation to
            # timeout by keeping RTTVAR=0 and then suddenly delaying packets by
            # D seconds. This counter-example is uninteresting. Hence
            # we usually want to avoid getting such counter-examples in
            # CCAC. Our timeout strategy sidesteps this issue.

            if t < c.R:
                s.add(v.timeout_f[n][t] == False)
            else:
                s.add(v.timeout_f[n][t] == And(
                    v.S_f[n][t - c.R] < v.A_f[n][t - 1],  # oustanding bytes
                    v.S_f[n][t - c.R] == v.A_f[n][t - c.R] -
                    v.L_f[n][t - c.R]))
            s.add(Implies(v.timeout_f[n][t], v.Ld_f[n][t] == v.L_f[n][t]))

            s.add(v.Ld_f[n][t] <= v.L_f[n][t - c.R])


def calculate_qdel(c: ModelConfig, s: MySolver, v: Variables):
    # Figure out the time when the bytes being output at time t were
    # first input

    # Note: We needn't calculate qdel per flow. That will relax unnecessarily,
    # allowing for more behaviors than admitted in the continuous model. One
    # qdel is enough because the *last* packet of each flow to have dequeued at
    # time t was enqueued between t-dt-1 and t-dt for all flows. Note, that
    # this property holds only for the last packet of each flow that gets
    # dequeued. This guarantee may or may not be enough for your use-case
    for t in range(c.T):
        for dt in range(c.T):
            if dt >= t:
                s.add(Not(v.qdel[t][dt]))
                continue
            s.add(v.qdel[t][dt] == Or(
                And(
                    v.S[t] != v.S[t - 1],
                    And(v.A[t - dt - 1] - v.L[t - dt - 1] < v.S[t],
                        v.A[t - dt] - v.L[t - dt] >= v.S[t])),
                And(v.S[t] == v.S[t - 1], v.qdel[t - 1][dt])))

        # We don't know what happened at t < 0, so we'll let the solver pick
        # non-deterministically
        s.add(
            Implies(And(v.S[t] != v.S[t - 1], v.A[0] - v.L[0] < v.S[t - 1]),
                    Not(v.qdel[t][t - 1])))


def multi_flows(c: ModelConfig, s: MySolver, v: Variables):
    assert (c.calculate_qdel)
    for t in range(c.T):
        for n in range(c.N):
            for dt in range(c.T):
                if t - dt - 1 < 0:
                    continue
                s.add(
                    Implies(v.qdel[t][dt], v.S_f[n][t] > v.A_f[n][t - dt - 1]))


def epsilon_alpha(c: ModelConfig, s: MySolver, v: Variables):
    if not c.compose:
        if c.epsilon == "zero":
            s.add(v.epsilon == 0)
        elif c.epsilon == "lt_alpha":
            s.add(v.epsilon < v.alpha)
        elif c.epsilon == "lt_half_alpha":
            s.add(v.epsilon < v.alpha * 0.5)
        elif c.epsilon == "gt_alpha":
            s.add(v.epsilon > v.alpha)
        else:
            assert (False)


def cwnd_rate_arrival(c: ModelConfig, s: MySolver, v: Variables):
    for n in range(c.N):
        for t in range(c.T):
            if t >= c.R:
                assert (c.R >= 1)
                # Arrival due to cwnd
                A_w = v.S_f[n][t - c.R] + v.Ld_f[n][t] + v.c_f[n][t]
                A_w = If(A_w >= v.A_f[n][t - 1], A_w, v.A_f[n][t - 1])
                # Arrival due to rate
                A_r = v.A_f[n][t - 1] + v.r_f[n][t]
                # Maximum arrival assuming app is backlogged
                max_arr = If(A_w >= A_r, A_r, A_w)
                if c.app == "bulk":
                    s.add(v.A_f[n][t] == max_arr)
                else:
                    # Min of what the CC and app can send
                    s.add(v.A_f[n][t] == If(max_arr <= v.av[n].snd[t], max_arr,
                                            v.av[n].snd[t]))
            else:
                # NOTE: This is different in this new version. Here anything
                # can happen. No restrictions
                pass


def min_send_quantum(c: ModelConfig, s: MySolver, v: Variables):
    '''Every timestep, the sender must send either 0 bytes or > 1MSS bytes.
    While it is not recommended that we use these constraints everywhere, in
    AIMD it is possible to not trigger loss detection by sending tiny packets
    which sum up to less than beta. However this is not possible in the real
    world and should be ruled out.
    '''

    for n in range(c.N):
        for t in range(1, c.T):
            s.add(
                Or(v.S_f[n][t - 1] == v.S_f[n][t],
                   v.S_f[n][t - 1] + v.alpha <= v.S_f[n][t]))


def cca_const(c: ModelConfig, s: MySolver, v: Variables):
    for n in range(c.N):
        for t in range(c.T):
            s.add(v.c_f[n][t] == v.alpha)

            if c.pacing:
                s.add(v.r_f[n][t] == v.alpha / c.R)
            else:
                s.add(v.r_f[n][t] >= c.C * 100)


def make_solver(c: ModelConfig) -> (MySolver, Variables):
    s = MySolver()
    v = Variables(c, s)

    if c.unsat_core:
        s.set(unsat_core=True)

    monotone(c, s, v)
    initial(c, s, v)
    relate_tot(c, s, v)
    network(c, s, v)
    loss_detected(c, s, v)
    epsilon_alpha(c, s, v)
    if c.calculate_qdel:
        calculate_qdel(c, s, v)
    if c.N > 1:
        assert (c.calculate_qdel)
        multi_flows(c, s, v)

    if c.app == "bulk":
        pass
    elif c.app == "bb_abr":
        # One config and variable object per flow
        c.ac = []
        v.av = []
        for n in range(c.N):
            ac, av = make_buffer_based_app(n, c, s, v)
            c.ac.append(ac)
            v.av.append(av)
    elif c.app == "panteabr":
        c.ac = []
        v.av = []
        for n in range(c.N):
            ac, av = make_panteabr_app(n, c, s, v)
            c.ac.append(ac)
            v.av.append(av)
    else:
        assert False, f"Unrecognized app: {c.app}"

    if c.cca == "const":
        cca_const(c, s, v)
    elif c.cca == "aimd":
        v.cv = cca_aimd(c, s, v)
    elif c.cca == "aimd_appsafe":
        v.cv = cca_aimd(c, s, v, appsafe=True)
    elif c.cca == "bbr":
        cca_bbr(c, s, v)
    elif c.cca == "copa":
        cca_copa(c, s, v)
    elif c.cca == "fair":
        cca_fair(c, s, v)
    elif c.cca == "rocc":
        v.cv = cca_rocc(c, s, v)
    elif c.cca == "conv":
        v.cv = cca_conv(c, s, v)
    elif c.cca == "any":
        pass
    else:
        assert (False)

    cwnd_rate_arrival(c, s, v)

    return (s, v)


if __name__ == "__main__":
    from cache import run_query
    from plot import plot_model
    from utils import make_periodic

    c = ModelConfig(N=2,
                    D=1,
                    R=1,
                    T=10,
                    C=1,
                    buf_min=None,
                    buf_max=None,
                    dupacks=None,
                    cca="const",
                    compose=True,
                    alpha=None,
                    pacing=False,
                    epsilon="zero",
                    unsat_core=True,
                    simplify=False)

    s, v = make_solver(c)
    dur = c.R + c.R + 2 * c.D
    # Consider the no loss case for simplicity
    s.add(v.L[0] == 0)
    s.add(v.alpha < 2)
    s.add(v.c_f[0][0] == v.c_f[1][0])
    s.add(v.A_f[0][0] == v.A_f[1][0])
    # s.add(v.A_f[0][0] == 0)
    # s.add(v.L[dur] == 0)
    # s.add(v.S[-1] - v.S[0] < c.C * (c.T - 1))
    s.add(v.S_f[0][-1] - v.S_f[1][-1] > 0.499 * c.C * c.T)
    make_periodic(c, s, v, dur)
    qres = run_query(s, c)
    print(qres.satisfiable)
    if str(qres.satisfiable) == "sat":
        plot_model(qres.model, c)
