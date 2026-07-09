# -*- coding: utf-8 -*-
"""
Tennis Doubles Scheduler v8 - Stable version with special court support
Handles odd-odd gender distributions (M%2=1, W%2=1, total%4=0)
using MXxWB (1M+3W) or MXxDB (3M+1W) special courts.
"""
import sys, os, random
from itertools import combinations

PRESETS = {}
PRESETS[(6,6)] = [
    (1,'DB',(0,1),(2,3)), (1,'WB',(0,1),(2,3)), (1,'MX',(4,4),(5,5)),
    (2,'DB',(0,5),(1,4)), (2,'WB',(0,4),(1,5)), (2,'MX',(2,2),(3,3)),
    (3,'DB',(1,2),(3,4)), (3,'WB',(0,3),(2,4)), (3,'MX',(0,5),(5,1)),
    (4,'DB',(0,3),(4,5)), (4,'WB',(1,2),(4,5)), (4,'MX',(1,0),(2,3)),
    (5,'DB',(0,4),(1,3)), (5,'WB',(0,2),(1,4)), (5,'MX',(2,5),(5,3)),
]
PRESETS[(4,4)] = [
    (1,'DB',(0,1),(2,3)), (1,'WB',(0,1),(2,3)),
    (2,'DB',(0,2),(1,3)), (2,'WB',(0,2),(1,3)),
    (3,'DB',(0,3),(1,2)), (3,'WB',(0,3),(1,2)),
    (4,'MX',(0,0),(1,1)), (4,'MX',(2,2),(3,3)),
    (5,'MX',(0,2),(1,3)), (5,'MX',(2,1),(3,0)),
]


def rr_pairs(N):
    """Standard round-robin pairs for N players (N even).
    Returns N-1 rounds of N/2 pairs, all pairs unique.
    Circle method: fix player N-1, rotate others around."""
    if N < 2 or N % 2 != 0: return []
    k = N - 1
    result = []
    for r in range(k):
        pairs = [(k, r)]
        for i in range(1, N // 2):
            a = (r + i) % k
            b = (r - i) % k
            if a != b:
                pairs.append((a, b))
        result.append(pairs)
    return result


def construct_dist(M, W, N):
    """
    Build court distribution for N rounds.
    Returns list of (a, b, c, special) entries per round.
    special: None | 'MXxWB' | 'MXxDB'
    """
    N = N or 5
    cp = (M + W) // 4

    # Detect special court needed (odd-odd, total multiple of 4)
    special = None
    M_base, W_base = M, W
    if M % 2 == 1 and W % 2 == 1 and (M + W) % 4 == 0:
        if M % 4 == 1 and W % 4 == 3:
            special = 'MXxWB'  # uses 1M + 3W
            M_base, W_base = M - 1, W - 3
        else:  # M%4==3, W%4==1
            special = 'MXxDB'  # uses 3M + 1W
            M_base, W_base = M - 3, W - 1

    remaining_courts = cp - (1 if special else 0)

    # Only the special court exists
    if remaining_courts == 0:
        return [(0, 0, 0, special)] * N

    # Uniform distribution (preferred)
    for c1 in [1, 2, 0]:
        if c1 > remaining_courts:
            continue
        if (M_base - 2 * c1) % 4 == 0 and (W_base - 2 * c1) % 4 == 0:
            a = (M_base - 2 * c1) // 4
            b = (W_base - 2 * c1) // 4
            if a >= 0 and b >= 0 and a + b + c1 == remaining_courts:
                return [(a, b, c1, special)] * N

    # Fallback: mixed distribution (two different round types)
    for c1 in range(remaining_courts + 1):
        for c2 in range(remaining_courts + 1):
            if c1 == c2:
                continue
            if (M_base - 2 * c1) % 4 != 0 or (W_base - 2 * c1) % 4 != 0:
                continue
            if (M_base - 2 * c2) % 4 != 0 or (W_base - 2 * c2) % 4 != 0:
                continue
            a1 = (M_base - 2 * c1) // 4
            b1 = (W_base - 2 * c1) // 4
            a2 = (M_base - 2 * c2) // 4
            b2 = (W_base - 2 * c2) // 4
            if a1 < 0 or b1 < 0 or a2 < 0 or b2 < 0:
                continue
            if a1 + b1 + c1 != remaining_courts or a2 + b2 + c2 != remaining_courts:
                continue
            for n1 in range(1, N):
                n2 = N - n1
                sc = n1 * c1 + n2 * c2
                sa = (N * M_base - 2 * sc) // 4
                sb = (N * W_base - 2 * sc) // 4
                if n1 * a1 + n2 * a2 == sa and n1 * b1 + n2 * b2 == sb:
                    d = [(a1, b1, c1, special)] * n1 + [(a2, b2, c2, special)] * n2
                    random.shuffle(d)
                    return d

    return None


def flex_pair(players, used, maxt=1000):
    """Flexible pairing without repeated partners."""
    pool = list(players)
    for _ in range(maxt):
        order = list(pool)
        random.shuffle(order)
        pairs = []
        seen = set()
        ok = True
        i = 0
        while i < len(order):
            p1 = order[i]
            found = False
            for j in range(i + 1, len(order)):
                p2 = order[j]
                fs = frozenset([p1, p2])
                if fs not in used and fs not in seen:
                    pairs.append((p1, p2))
                    seen.add(fs)
                    order.pop(j)
                    order.pop(i)
                    found = True
                    break
            if not found:
                ok = False
                break
        if ok:
            for s in seen:
                used.add(s)
            random.shuffle(pairs)
            return [(pairs[k], pairs[k + 1]) for k in range(0, len(pairs), 2)]
    return None


def flex_mix(males, females, used, maxt=1000):
    ml = list(males)
    for _ in range(maxt):
        fl = list(females)
        random.shuffle(ml)
        random.shuffle(fl)
        pairs = []
        seen = set()
        ok = True
        for m in ml:
            found = False
            for fi, w in enumerate(fl):
                if (m, w) not in used and (m, w) not in seen:
                    pairs.append((m, w))
                    seen.add((m, w))
                    fl.pop(fi)
                    found = True
                    break
            if not found:
                ok = False
                break
        if ok:
            for p in seen:
                used.add(p)
            random.shuffle(pairs)
            return [(pairs[k], pairs[k + 1]) for k in range(0, len(pairs), 2)]
    return None


# ---------------------------------------------------------------------------
# Special court helpers
# ---------------------------------------------------------------------------

def _pick_special_court_mxwb(rnd, M, W, used_mx_pairs, used_wb_pairs):
    """
    Pick 1 man (for MX side) + partner woman + 2 other women (WB side).
    Returns (man_idx, mx_woman_idx, wb_woman0, wb_woman1) or None.
    Rotates selections to ensure fairness.
    """
    # Try all combinations, preferring smart rotation
    men_order = list(range(M))
    women_order = list(range(W))

    # Rotate which man plays the special court
    start_m = rnd % M
    for mi in range(M):
        m_idx = men_order[(start_m + mi) % M]

        # Rotate which woman is the MX partner
        start_w = (rnd + mi) % W
        for wi in range(W):
            w_mx = women_order[(start_w + wi) % W]
            mx_key = (m_idx, w_mx)
            if mx_key in used_mx_pairs:
                continue

            # Remaining women for WB side
            rest_w = [w for w in women_order if w != w_mx]
            # Try all WB pair combos
            for wb_i in range(len(rest_w) - 1):
                for wb_j in range(wb_i + 1, len(rest_w)):
                    wb0, wb1 = rest_w[wb_i], rest_w[wb_j]
                    wb_key = frozenset([wb0, wb1])
                    if wb_key in used_wb_pairs:
                        continue
                    return (m_idx, w_mx, wb0, wb1)

    # If all MD pairs are exhausted, accept repeat (cycle)
    for mi in range(M):
        m_idx = men_order[(start_m + mi) % M]
        for wi in range(W):
            w_mx = women_order[(start_w + wi) % W]
            rest_w = [w for w in women_order if w != w_mx]
            # Accept any remaining pair
            for wb_i in range(len(rest_w) - 1):
                for wb_j in range(wb_i + 1, len(rest_w)):
                    wb0, wb1 = rest_w[wb_i], rest_w[wb_j]
                    return (m_idx, w_mx, wb0, wb1)
    return None


def _pick_special_court_mxdb(rnd, M, W, used_mx_pairs, used_db_pairs):
    """
    Pick 1 woman (for MX side) + partner man + 2 other men (DB side).
    Returns (mx_man_idx, woman_idx, db_man0, db_man1) or None.
    """
    men_order = list(range(M))
    women_order = list(range(W))

    start_w = rnd % W
    for wi in range(W):
        w_idx = women_order[(start_w + wi) % W]

        # Rotate which man is the MX partner
        start_m = (rnd + wi) % M
        for mi in range(M):
            m_mx = men_order[(start_m + mi) % M]
            mx_key = (m_mx, w_idx)
            if mx_key in used_mx_pairs:
                continue

            rest_m = [m for m in men_order if m != m_mx]
            for db_i in range(len(rest_m) - 1):
                for db_j in range(db_i + 1, len(rest_m)):
                    db0, db1 = rest_m[db_i], rest_m[db_j]
                    db_key = frozenset([db0, db1])
                    if db_key in used_db_pairs:
                        continue
                    return (m_mx, w_idx, db0, db1)

    # Accept repeat
    for wi in range(W):
        w_idx = women_order[(start_w + wi) % W]
        for mi in range(M):
            m_mx = men_order[(start_m + mi) % M]
            rest_m = [m for m in men_order if m != m_mx]
            for db_i in range(len(rest_m) - 1):
                for db_j in range(db_i + 1, len(rest_m)):
                    db0, db1 = rest_m[db_i], rest_m[db_j]
                    return (m_mx, w_idx, db0, db1)
    return None


# =======================================================================
# Plan A — Deterministic graph matching (Hungarian + enumeratePairings)
# =======================================================================

INF = 1e9


def enumerate_pairings(players, levels, used_pairs, opp_counters, gender):
    """Enumerate all 3 pairings of 4 players, pick best by score."""
    a, b, c, d = players
    g = gender or 'M'

    def _score(p1, p2):
        k1 = g + str(min(p1)) + ',' + g + str(max(p1))
        k2 = g + str(min(p2)) + ',' + g + str(max(p2))
        s = 0.0
        s += abs((levels[p1[0]] if p1[0] < len(levels) else 3.0) - (levels[p1[1]] if p1[1] < len(levels) else 3.0))
        s += abs((levels[p2[0]] if p2[0] < len(levels) else 3.0) - (levels[p2[1]] if p2[1] < len(levels) else 3.0))
        sum1 = (levels[p1[0]] if p1[0] < len(levels) else 3.0) + (levels[p1[1]] if p1[1] < len(levels) else 3.0)
        sum2 = (levels[p2[0]] if p2[0] < len(levels) else 3.0) + (levels[p2[1]] if p2[1] < len(levels) else 3.0)
        s += abs(sum1 - sum2) * 10
        if k1 in used_pairs if hasattr(used_pairs, '__contains__') else False:
            s += INF
        if k2 in used_pairs if hasattr(used_pairs, '__contains__') else False:
            s += INF
        if opp_counters:
            cross = [
                g + str(min(p1[0], p2[0])) + ',' + g + str(max(p1[0], p2[0])),
                g + str(min(p1[0], p2[1])) + ',' + g + str(max(p1[0], p2[1])),
                g + str(min(p1[1], p2[0])) + ',' + g + str(max(p1[1], p2[0])),
                g + str(min(p1[1], p2[1])) + ',' + g + str(max(p1[1], p2[1])),
            ]
            for ck in cross:
                cnt = opp_counters.get(ck, 0)
                if cnt > 0:
                    s += cnt * 10000
        return s

    candidates = [
        ([(a, b), (c, d)], _score([a, b], [c, d])),
        ([(a, c), (b, d)], _score([a, c], [b, d])),
        ([(a, d), (b, c)], _score([a, d], [b, c])),
    ]
    best = None
    best_score = INF
    for pairs, sc in candidates:
        if sc < best_score:
            best_score = sc
            best = pairs
    if best is None:
        return None
    # When scores equal, shuffle to provide diversity (breaks deterministic ties)
    if best_score < INF / 10:
        tied = [(p, s) for p, s in candidates if abs(s - best_score) < 0.001]
        if len(tied) > 1:
            import random
            best = random.choice(tied)[0]
    return {'pairs': best, 'score': best_score}


def hungarian(cost_matrix):
    """Standard Hungarian algorithm for minimum weight perfect matching.
    Input: n x n cost matrix. Output: assignment list [col_for_row0, ...]."""
    n = len(cost_matrix)
    if n == 0:
        return []
    u = [0] * (n + 1)
    v = [0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)

    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = INF
            j1 = 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost_matrix[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(0, n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    assignment = [0] * n
    for j in range(1, n + 1):
        assignment[p[j] - 1] = j - 1
    return assignment


def build_cost_matrix(men, women, used_mx_pairs, male_levels, female_levels, opp_counters=None):
    """Build MX pairing cost matrix: |level_diff| + pairRepeatINF + oppPenalty."""
    m = len(men)
    w = len(women)
    matrix = []
    for mi in range(m):
        row = []
        man_idx = men[mi]
        for wi in range(w):
            woman_idx = women[wi]
            cost = abs((male_levels[man_idx] if man_idx < len(male_levels) else 3.0)
                       - (female_levels[woman_idx] if woman_idx < len(female_levels) else 3.0))
            pair_key = str(man_idx) + ',M' + str(woman_idx)
            if used_mx_pairs and pair_key in used_mx_pairs:
                cost += INF
            # Opponent awareness: penalize if man|woman already face many opponents
            if opp_counters:
                for other_m in men:
                    if other_m == man_idx:
                        continue
                    mk = 'M' + str(min(man_idx, other_m)) + ',M' + str(max(man_idx, other_m))
                    cnt = opp_counters.get(mk, 0)
                    if cnt > 0:
                        cost += cnt * 5000
                for other_w in women:
                    if other_w == woman_idx:
                        continue
                    wk = 'W' + str(min(woman_idx, other_w)) + ',W' + str(max(woman_idx, other_w))
                    cnt = opp_counters.get(wk, 0)
                    if cnt > 0:
                        cost += cnt * 5000
            row.append(cost)
        matrix.append(row)
    return matrix


def _pick_xw(rnd, M, W, used_smx, used_swb, male_levels, female_levels):
    """Pick special court MXxWB (1M+3W) with level awareness."""
    def xw_score(m_idx, w_mx, wb0, wb1):
        t1 = (male_levels[m_idx] if m_idx < len(male_levels) else 3.0) + (female_levels[w_mx] if w_mx < len(female_levels) else 3.0)
        t2 = (female_levels[wb0] if wb0 < len(female_levels) else 3.0) + (female_levels[wb1] if wb1 < len(female_levels) else 3.0)
        return abs(t1 - t2)

    best = None
    best_score = INF
    best_repeat = None
    best_repeat_score = INF
    start_m = rnd % M
    start_w_base = rnd % W
    for mi in range(M):
        m_idx = (start_m + mi) % M
        start_w = (start_w_base + mi) % W
        for wi in range(W):
            w_mx = (start_w + wi) % W
            mx_key = str(m_idx) + ',' + str(w_mx)
            rest_w = [w for w in range(W) if w != w_mx]
            for wbi in range(len(rest_w) - 1):
                for wbj in range(wbi + 1, len(rest_w)):
                    wb_key = str(min(rest_w[wbi], rest_w[wbj])) + ',' + str(max(rest_w[wbi], rest_w[wbj]))
                    sc = xw_score(m_idx, w_mx, rest_w[wbi], rest_w[wbj])
                    if mx_key not in used_smx and wb_key not in used_swb:
                        if sc < best_score:
                            best_score = sc
                            best = [m_idx, w_mx, rest_w[wbi], rest_w[wbj]]
                    else:
                        if sc < best_repeat_score:
                            best_repeat_score = sc
                            best_repeat = [m_idx, w_mx, rest_w[wbi], rest_w[wbj]]
    return best or best_repeat or None


def _pick_xd(rnd, M, W, used_smx, used_sdb, male_levels, female_levels):
    """Pick special court MXxDB (3M+1W) with level awareness."""
    def xd_score(m_mx, w_idx, db0, db1):
        t1 = (male_levels[m_mx] if m_mx < len(male_levels) else 3.0) + (female_levels[w_idx] if w_idx < len(female_levels) else 3.0)
        t2 = (male_levels[db0] if db0 < len(male_levels) else 3.0) + (male_levels[db1] if db1 < len(male_levels) else 3.0)
        return abs(t1 - t2)

    best = None
    best_score = INF
    best_repeat = None
    best_repeat_score = INF
    start_w = rnd % W
    start_m_base = rnd % M
    for wi in range(W):
        w_idx = (start_w + wi) % W
        start_m = (start_m_base + wi) % M
        for mi in range(M):
            m_mx = (start_m + mi) % M
            mx_key = str(m_mx) + ',' + str(w_idx)
            rest_m = [m for m in range(M) if m != m_mx]
            for dbi in range(len(rest_m) - 1):
                for dbj in range(dbi + 1, len(rest_m)):
                    db_key = str(min(rest_m[dbi], rest_m[dbj])) + ',' + str(max(rest_m[dbi], rest_m[dbj]))
                    sc = xd_score(m_mx, w_idx, rest_m[dbi], rest_m[dbj])
                    if mx_key not in used_smx and db_key not in used_sdb:
                        if sc < best_score:
                            best_score = sc
                            best = [m_mx, w_idx, rest_m[dbi], rest_m[dbj]]
                    else:
                        if sc < best_repeat_score:
                            best_repeat_score = sc
                            best_repeat = [m_mx, w_idx, rest_m[dbi], rest_m[dbj]]
    return best or best_repeat or None


def _build_diverse_group(avail, group_size, group_book, appearances, used_pairs, gender):
    """
    Greedily build a group from `avail` of size `group_size`.
    Each pick maximizes diversity: prefers players who have co-appeared with
    already-selected players the fewest times (group_book).
    Ties -> fewer appearances, then more unused partners.
    """
    if group_size <= 0:
        return []
    if len(avail) < group_size:
        return None
    remaining = list(avail)
    selected = []
    while len(selected) < group_size:
        best_p = None
        best_key = (99999, 99999, -99999, 99999)
        for p in remaining:
            co_sum = sum(group_book.get(tuple(sorted([p, s])), 0) for s in selected)
            app = appearances[p] if appearances else 0
            unused = 0
            for p2 in avail:
                if p2 == p: continue
                pk = gender + str(min(p, p2)) + ',' + gender + str(max(p, p2))
                if pk not in used_pairs:
                    unused += 1
            key = (co_sum, app, -unused, p)
            if key < best_key:
                best_key = key
                best_p = p
        if best_p is None:
            return None
        selected.append(best_p)
        remaining.remove(best_p)
    return selected


def allocate_players(avail_m, avail_w, need_db, need_wb, need_mx,
                     male_levels, female_levels, used_pairs, opp_counters,
                     round_idx=0, db_appearances=None, wb_appearances=None,
                     db_group_book=None, wb_group_book=None):
    """
    Plan B Enhanced — Diversity-aware grouping engine.
    Assigns players to DB/WB/MX groups.
    Uses db_group_book/wb_group_book to avoid repeatedly grouping the same players.
    Returns (group_db, group_wb, group_mx_men, group_mx_women) or None.
    """
    db_group_book = db_group_book or {}
    wb_group_book = wb_group_book or {}

    if need_db > 0:
        group_db = _build_diverse_group(avail_m, need_db, db_group_book,
                                         db_appearances or [], used_pairs, 'M')
        if group_db is None:
            return None
        group_mx_men = [p for p in avail_m if p not in group_db][:need_mx]
    else:
        group_db = []
        group_mx_men = sorted(avail_m, key=lambda p: (db_appearances[p] if db_appearances else 0, p))[:need_mx]

    if need_wb > 0:
        group_wb = _build_diverse_group(avail_w, need_wb, wb_group_book,
                                         wb_appearances or [], used_pairs, 'W')
        if group_wb is None:
            return None
        group_mx_women = [p for p in avail_w if p not in group_wb][:need_mx]
    else:
        group_wb = []
        group_mx_women = sorted(avail_w, key=lambda p: (wb_appearances[p] if wb_appearances else 0, p))[:need_mx]

    # Validate counts
    if len(group_db) != need_db or len(group_wb) != need_wb:
        return None
    if len(group_mx_men) != need_mx or len(group_mx_women) != need_mx:
        return None
    if len(group_mx_men) != len(group_mx_women):
        return None
    if len(group_db) % 4 != 0:
        return None
    if len(group_wb) % 4 != 0:
        return None

    return group_db, group_wb, group_mx_men, group_mx_women


def go_exact(M, W, dist, is_uniform, N, male_levels, female_levels, round_counters=None, opp_counters=None):
    """Deterministic replacement for _go().
    DB/WB: enumerate_pairings picks best (among 3 pairings for 4 players)
    MX: Hungarian algorithm for optimal pairing
    Special court (XW/XD): deterministic rotation with level balance
    N-round constraints: roundCounters ensures total placement across rounds
    Plan B Step 1+2: opp_counters in MX, unified group allocation
    """
    opp_counters = opp_counters or {}
    round_counters = round_counters or {}
    matches = []
    used_pairs = set()
    used_mx_pairs = set()
    used_smx = set()
    used_swb = set()
    used_sdb = set()
    # Track how many times each player has been assigned to DB/WB for rotation balance
    db_appearances = [0] * M
    wb_appearances = [0] * W
    # Track how many times each pair has been in the same DB/WB group (diversity tracking)
    db_group_book = {}
    wb_group_book = {}

    def _mark_pair(a, b, g):
        used_pairs.add(g + str(min(a, b)) + ',' + g + str(max(a, b)))

    def _add_opp(a, b, g):
        key = g + str(min(a, b)) + ',' + g + str(max(a, b))
        opp_counters[key] = opp_counters.get(key, 0) + 1

    for r in range(N):
        d = dist[r]
        a, b, c, special = d[0], d[1], d[2], d[3]
        need_db = 4 * a
        need_wb = 4 * b
        need_mx = 2 * c

        # Compute who still needs to play this round
        mc = [0] * M
        fc = [0] * W
        for m_entry in matches:
            typ = m_entry[1]
            t1, t2 = m_entry[2], m_entry[3]
            if typ == 'DB':
                for p in t1:
                    mc[p] += 1
                for p in t2:
                    mc[p] += 1
            elif typ == 'WB':
                for p in t1:
                    fc[p] += 1
                for p in t2:
                    fc[p] += 1
            elif typ == 'MX':
                mc[t1[0]] += 1
                mc[t2[0]] += 1
                fc[t1[1]] += 1
                fc[t2[1]] += 1
            elif typ == 'XW':
                mc[t1[0]] += 1
                fc[t1[1]] += 1
                fc[t2[0]] += 1
                fc[t2[1]] += 1
            elif typ == 'XD':
                mc[t1[0]] += 1
                mc[t2[0]] += 1
                mc[t2[1]] += 1
                fc[t1[1]] += 1

        spec_m = []
        spec_w = []

        # --- Special court placement (XW/XD) ---
        if special == 'XW':
            p = _pick_xw(r, M, W, used_smx, used_swb, male_levels, female_levels)
            if not p:
                return None
            sm, sw_mx, swb0, swb1 = p
            spec_m.append(sm)
            spec_w.extend([sw_mx, swb0, swb1])
            used_smx.add(str(sm) + ',' + str(sw_mx))
            used_swb.add(str(min(swb0, swb1)) + ',' + str(max(swb0, swb1)))
            matches.append((r + 1, 'XW', (sm, sw_mx), (swb0, swb1)))
            # Opponent records: MX woman vs each WB woman
            _add_opp(sw_mx, swb0, 'W')
            _add_opp(sw_mx, swb1, 'W')
        elif special == 'XD':
            p = _pick_xd(r, M, W, used_smx, used_sdb, male_levels, female_levels)
            if not p:
                return None
            sm_mx, sw, sdb0, sdb1 = p
            spec_m.extend([sm_mx, sdb0, sdb1])
            spec_w.append(sw)
            used_smx.add(str(sm_mx) + ',' + str(sw))
            used_sdb.add(str(min(sdb0, sdb1)) + ',' + str(max(sdb0, sdb1)))
            matches.append((r + 1, 'XD', (sm_mx, sw), (sdb0, sdb1)))
            # Opponent records: MX man vs each DB man
            _add_opp(sm_mx, sdb0, 'M')
            _add_opp(sm_mx, sdb1, 'M')

        # --- roundCounters: place N-round fixed constraints ---
        if round_counters:
            rc_keys = list(round_counters.keys())
            for rck in rc_keys:
                rc = round_counters[rck]
                if not rc or rc['remaining'] <= 0:
                    continue
                fc = rc['constraint']
                genders = fc['genders'] if isinstance(fc, dict) else fc.genders
                is_db = genders == 'MMMM'
                is_wb = genders == 'WWWW'
                is_mx = genders in ('MWMW', 'WMWM', 'MWWM', 'WMMW')
                is_xw = genders in ('MWWW', 'WMWW', 'WWMW')
                is_xd = genders in ('MMMW', 'MWMM', 'MMWM')
                if is_xw or is_xd:
                    continue
                need = 4 if is_db or is_wb else 2
                has_capacity = False
                if is_db and need_db >= need:
                    has_capacity = True
                elif is_wb and need_wb >= need:
                    has_capacity = True
                elif is_mx and need_mx >= need:
                    has_capacity = True
                if not has_capacity:
                    continue
                if is_db:
                    need_db -= 4
                    spec_m.extend([fc['a'], fc['b'], fc['c'], fc['d']])
                    matches.append((r + 1, 'DB', (fc['a'], fc['b']), (fc['c'], fc['d'])))
                elif is_wb:
                    need_wb -= 4
                    spec_w.extend([fc['a'], fc['b'], fc['c'], fc['d']])
                    matches.append((r + 1, 'WB', (fc['a'], fc['b']), (fc['c'], fc['d'])))
                elif is_mx:
                    need_mx -= 2
                    m1 = fc['a'] if genders[0] == 'M' else fc['b']
                    w1 = fc['b'] if genders[0] == 'M' else fc['a']
                    m2 = fc['c'] if genders[2] == 'M' else fc['d']
                    w2 = fc['d'] if genders[2] == 'M' else fc['c']
                    spec_m.extend([m1, m2])
                    spec_w.extend([w1, w2])
                    matches.append((r + 1, 'MX', (m1, w1), (m2, w2)))
                rc['remaining'] -= 1
                break

        avail_m = [mi for mi in range(M) if mc[mi] == r and mi not in spec_m]
        avail_w = [wi for wi in range(W) if fc[wi] == r and wi not in spec_w]

        # --- Plan B Enhanced: Diversity-aware grouping ---
        if need_db > 0 or need_wb > 0 or need_mx > 0:
            alloc = allocate_players(avail_m, avail_w, need_db, need_wb, need_mx,
                                    male_levels, female_levels, used_pairs, opp_counters,
                                    round_idx=r, db_appearances=db_appearances,
                                    wb_appearances=wb_appearances,
                                    db_group_book=db_group_book, wb_group_book=wb_group_book)
            if alloc is None:
                return None
            group_db, group_wb, group_mx_men, group_mx_women = alloc
            # Update group diversity tracking
            for a in group_db:
                for b in group_db:
                    if a < b:
                        db_group_book[(a, b)] = db_group_book.get((a, b), 0) + 1
            for a in group_wb:
                for b in group_wb:
                    if a < b:
                        wb_group_book[(a, b)] = wb_group_book.get((a, b), 0) + 1
        else:
            group_db, group_wb, group_mx_men, group_mx_women = [], [], [], []

        # --- DB ---
        if len(group_db) > 0:
            for di in range(0, len(group_db), 4):
                four = group_db[di:di + 4]
                if len(four) < 4:
                    continue
                ep = enumerate_pairings(four, male_levels, used_pairs, opp_counters, 'M')
                if not ep:
                    return None
                p1, p2 = ep['pairs'][0], ep['pairs'][1]
                matches.append((r + 1, 'DB', p1, p2))
                _mark_pair(p1[0], p1[1], 'M')
                _mark_pair(p2[0], p2[1], 'M')
                _add_opp(p1[0], p2[0], 'M')
                _add_opp(p1[0], p2[1], 'M')
                _add_opp(p1[1], p2[0], 'M')
                _add_opp(p1[1], p2[1], 'M')
                for _dp in four:
                    db_appearances[_dp] += 1

        # --- WB ---
        if len(group_wb) > 0:
            for wi_idx in range(0, len(group_wb), 4):
                four = group_wb[wi_idx:wi_idx + 4]
                if len(four) < 4:
                    continue
                ep = enumerate_pairings(four, female_levels, used_pairs, opp_counters, 'W')
                if not ep:
                    return None
                p1, p2 = ep['pairs'][0], ep['pairs'][1]
                matches.append((r + 1, 'WB', p1, p2))
                _mark_pair(p1[0], p1[1], 'W')
                _mark_pair(p2[0], p2[1], 'W')
                _add_opp(p1[0], p2[0], 'W')
                _add_opp(p1[0], p2[1], 'W')
                _add_opp(p1[1], p2[0], 'W')
                _add_opp(p1[1], p2[1], 'W')
                for _wp in four:
                    wb_appearances[_wp] += 1

        # --- MX (with opp_counters in build_cost_matrix) ---
        if len(group_mx_men) > 0:
            if len(group_mx_men) != len(group_mx_women):
                return None
            matrix = build_cost_matrix(group_mx_men, group_mx_women, used_mx_pairs, male_levels, female_levels, opp_counters)
            if not matrix or len(matrix) != len(matrix[0]):
                return None
            all_zero = all(matrix[mi][wi] == 0 for mi in range(len(matrix)) for wi in range(len(matrix[0])))
            if all_zero:
                # Opponent-aware pairing: try all permutations, pick best (min max_opp, then min total)
                n_men = len(group_mx_men)
                best_assign = None
                best_max_opp = INF
                best_total_opp = INF
                from itertools import permutations
                for perm in permutations(range(n_men)):
                    opp_score = 0
                    max_opp = 0
                    for ci in range(n_men // 2):
                        w1_idx = perm[2*ci]
                        w2_idx = perm[2*ci+1]
                        m1 = group_mx_men[2*ci]
                        m2 = group_mx_men[2*ci+1]
                        mk = 'M' + str(min(m1,m2)) + ',M' + str(max(m1,m2))
                        wk = 'W' + str(min(group_mx_women[w1_idx], group_mx_women[w2_idx])) + ',W' + str(max(group_mx_women[w1_idx], group_mx_women[w2_idx]))
                        mc = opp_counters.get(mk, 0)
                        wc = opp_counters.get(wk, 0)
                        opp_score += mc + wc
                        max_opp = max(max_opp, mc, wc)
                    if max_opp < best_max_opp or (max_opp == best_max_opp and opp_score < best_total_opp):
                        best_max_opp = max_opp
                        best_total_opp = opp_score
                        best_assign = perm
                assign = list(best_assign) if best_assign else list(range(n_men))
            else:
                assign = hungarian(matrix)
            mx_matches = len(group_mx_men) // 2
            for ci in range(mx_matches):
                wi1 = assign[2 * ci]
                wi2 = assign[2 * ci + 1]
                t1 = (group_mx_men[2 * ci], group_mx_women[wi1])
                t2 = (group_mx_men[2 * ci + 1], group_mx_women[wi2])
                m_key = 'M' + str(min(t1[0], t2[0])) + ',M' + str(max(t1[0], t2[0]))
                w_key = 'W' + str(min(t1[1], t2[1])) + ',W' + str(max(t1[1], t2[1]))
                matches.append((r + 1, 'MX', t1, t2))
                used_mx_pairs.add(str(t1[0]) + ',M' + str(t1[1]))
                used_mx_pairs.add(str(t2[0]) + ',M' + str(t2[1]))
                opp_counters[m_key] = opp_counters.get(m_key, 0) + 1
                opp_counters[w_key] = opp_counters.get(w_key, 0) + 1

    # Verify match counts
    fmc = [0] * M
    ffc = [0] * W
    for m_entry in matches:
        typ = m_entry[1]
        t1, t2 = m_entry[2], m_entry[3]
        if typ == 'DB' or typ == 'MB':
            for p in t1:
                fmc[p] += 1
            for p in t2:
                fmc[p] += 1
        elif typ == 'WB':
            for p in t1:
                ffc[p] += 1
            for p in t2:
                ffc[p] += 1
        elif typ == 'MX':
            fmc[t1[0]] += 1
            fmc[t2[0]] += 1
            ffc[t1[1]] += 1
            ffc[t2[1]] += 1
        elif typ == 'XW':
            fmc[t1[0]] += 1
            ffc[t1[1]] += 1
            ffc[t2[0]] += 1
            ffc[t2[1]] += 1
        elif typ == 'XD':
            fmc[t1[0]] += 1
            fmc[t2[0]] += 1
            fmc[t2[1]] += 1
            ffc[t1[1]] += 1

    if not all(v == N for v in fmc) or not all(v == N for v in ffc):
        return None

    # Post-processing: 2-opt local search to reduce opponent repetition
    matches = _local_search_opp(matches, M, W, iterations=2000)

    return matches


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def _compute_opp_stats(matches, M, W):
    """Compute opponent encounter statistics for all matches.
    Returns (max_opp, total_opp, opp_counts_dict).
    """
    from collections import defaultdict
    opp = defaultdict(int)
    for m in matches:
        typ = m[1]
        t1, t2 = m[2], m[3]
        for a in t1:
            for b in t2:
                key = tuple(sorted([a, b]))
                opp[key] += 1
    max_opp = max(opp.values()) if opp else 0
    over3 = {k: v for k, v in opp.items() if v >= 3}
    return max_opp, sum(opp.values()), opp, over3


def _local_search_opp(matches, M, W, iterations=2000):
    """2-opt local search to reduce opponent repetition.
    Swaps full teams between two same-type same-round matches.
    Returns improved matches list (or original if no improvement).
    """
    from collections import defaultdict

    def _compute(mlist):
        opp = defaultdict(int)
        for m in mlist:
            t1, t2 = m[2], m[3]
            for a in t1:
                for b in t2:
                    key = tuple(sorted([a, b]))
                    opp[key] += 1
        maxv = max(opp.values()) if opp else 0
        over3 = sum(1 for v in opp.values() if v >= 3)
        return maxv, over3, opp

    best = list(matches)
    best_max, best_over3, _ = _compute(best)

    # Group indices by (round, type)
    groups = defaultdict(list)
    for i, m in enumerate(best):
        groups[(m[0], m[1])].append(i)

    for _ in range(iterations):
        # Pick a random group with at least 2 matches
        viable = [(r, t) for (r, t), idxs in groups.items() if len(idxs) >= 2]
        if not viable:
            break
        rnd_type = random.choice(viable)
        idxs = groups[rnd_type]
        i, j = random.sample(idxs, 2)
        m1, m2 = best[i], best[j]
        typ = rnd_type[1]
        t1a, t1b = m1[2], m1[3]
        t2a, t2b = m2[2], m2[3]

        if typ in ('DB', 'WB'):
            # 4 possible team swaps between two matches
            for na, nb in [(t1a, t2a), (t1a, t2b), (t1b, t2a), (t1b, t2b)]:
                other_m1 = t1b if na == t1a else t1a
                other_m2 = t2b if nb == t2a else t2a
                # Check no duplicate player in same team
                if len(set(na + other_m1)) < 4 or len(set(nb + other_m2)) < 4:
                    continue
                cand = list(best)
                cand[i] = (m1[0], typ, na, other_m1)
                cand[j] = (m2[0], typ, nb, other_m2)
                cmax, cover3, _ = _compute(cand)
                if cmax < best_max or (cmax == best_max and cover3 < best_over3):
                    best = cand
                    best_max, best_over3 = cmax, cover3
                    break  # accept first improvement, restart
        elif typ == 'MX':
            # Swap women between MX matches: (m_a, w_a) vs (m_b, w_b)  and  (m_c, w_c) vs (m_d, w_d)
            # Try cross-woman assignments
            for wa1, wb1, wc1, wd1 in [
                (t1a[1], t2a[1], t1b[1], t2b[1]),
                (t1a[1], t2b[1], t1b[1], t2a[1]),
            ]:
                if len({wa1, wb1, wc1, wd1}) < 4:
                    continue
                cand = list(best)
                cand[i] = (m1[0], typ, (t1a[0], wa1), (t1b[0], wb1))
                cand[j] = (m2[0], typ, (t2a[0], wc1), (t2b[0], wd1))
                cmax, cover3, _ = _compute(cand)
                if cmax < best_max or (cmax == best_max and cover3 < best_over3):
                    best = cand
                    best_max, best_over3 = cmax, cover3
                    break

    return best


def _opponent_stats(matches):
    """Compute opponent encounter stats.
    Returns (max_opp_count, over3_count).
    """
    from collections import defaultdict
    opp = defaultdict(int)
    for m in matches:
        t1, t2 = m[2], m[3]
        for a in t1:
            for b in t2:
                opp[tuple(sorted([a, b]))] += 1
    maxv = max(opp.values()) if opp else 0
    over3 = sum(1 for v in opp.values() if v >= 3)
    return maxv, over3


def _verify_opponent_limit(matches, M, W):
    """Check that no pair of players face each other >2 times."""
    from collections import defaultdict
    opp = defaultdict(int)
    for m in matches:
        typ = m[1]
        t1, t2 = m[2], m[3]
        for a in t1:
            for b in t2:
                key = tuple(sorted([a, b]))
                opp[key] += 1
    over2 = {k: v for k, v in opp.items() if v > 2}
    return len(over2) == 0


def gen(M, W, N=5, tries=3000):
    if (M, W) in PRESETS and N == 5:
        return _fmt(PRESETS[(M, W)], M, W, N)
    dist = construct_dist(M, W, N)
    if not dist:
        return f"Error: no feasible dist (M={M},W={W},N={N})"
    is_uniform = all(d == dist[0] for d in dist)

    male_levels = [3.0] * M
    female_levels = [3.0] * W

    # Try go_exact with uniform levels
    r = go_exact(M, W, dist, is_uniform, N, male_levels, female_levels)
    if r:
        return _fmt(r, M, W, N)

    # Try go_exact with slight level variation to break uniform-level ties
    for seed in range(10):
        varied_m = [(3.0 + (i + seed) * 0.01 % 1.0) for i in range(M)]
        varied_f = [(3.0 + (i + seed * 2) * 0.01 % 1.0) for i in range(W)]
        r = go_exact(M, W, dist, is_uniform, N, varied_m, varied_f)
        if r:
            return _fmt(r, M, W, N)

    # Fallback: collect multiple _go() results, pick best by opponent stats
    candidates = []
    total_attempts = min(tries, 500)  # Cap fallback attempts
    for attempt in range(total_attempts):
        r_matches = _go(M, W, dist, is_uniform, N)
        if r_matches:
            max_opp, over3 = _opponent_stats(r_matches)
            candidates.append((max_opp, over3, r_matches))
            if max_opp <= 2 and over3 == 0:
                break  # Found clean solution

    if not candidates:
        return f"Warning: no schedule (M={M},W={W}) after {total_attempts} tries"

    # Pick best by (max_opp ASC, over3 ASC)
    candidates.sort(key=lambda x: (x[0], x[1]))
    best_matches = candidates[0][2]

    # Apply local search only on the best candidate
    best_matches = _local_search_opp(best_matches, M, W, iterations=2000)
    return _fmt(best_matches, M, W, N)


def _go(M, W, dist, is_uniform, N=5):
    # Compute standard court totals (exclude special court)
    sa = sum(a for a, b, c, s in dist)
    sb = sum(b for a, b, c, s in dist)
    sc = sum(c for a, b, c, s in dist)

    # Distribute standard court appearances among players
    db_tgt = [4 * sa // M] * M
    for i in range((4 * sa) % M):
        db_tgt[i] += 1
    wb_tgt = [4 * sb // W] * W
    for i in range((4 * sb) % W):
        wb_tgt[i] += 1

    db_left = list(db_tgt)
    wb_left = list(wb_tgt)
    used_db = set()
    used_wb = set()
    used_mx = set()
    # Special court tracking
    used_smx = set()  # (man, woman) pairs for special court MX side
    used_swb = set()  # frozenset(2 women) for MXxWB WB side
    used_sdb = set()  # frozenset(2 men) for MXxDB DB side

    rr_db = rr_pairs(M)
    rr_wb = rr_pairs(W)

    matches = []
    special_count = {}  # Counter for which women/men get special court

    for r in range(N):
        a, b, c, special = dist[r]
        need_db = 4 * a
        need_wb = 4 * b
        need_mx = 2 * c

        # ---- Determine special court allocation (if any) ----
        spec_m = []   # men used in special court
        spec_w = []   # women used in special court

        if special == 'MXxWB':
            picked = _pick_special_court_mxwb(r, M, W, used_smx, used_swb)
            if not picked:
                return None
            sm, sw_mx, swb0, swb1 = picked
            spec_m = [sm]
            spec_w = [sw_mx, swb0, swb1]
            used_smx.add((sm, sw_mx))
            used_swb.add(frozenset([swb0, swb1]))
            matches.append((r + 1, 'XW', (sm, sw_mx), (swb0, swb1)))

        elif special == 'MXxDB':
            picked = _pick_special_court_mxdb(r, M, W, used_smx, used_sdb)
            if not picked:
                return None
            sm_mx, sw, sdb0, sdb1 = picked
            spec_m = [sm_mx, sdb0, sdb1]
            spec_w = [sw]
            used_smx.add((sm_mx, sw))
            used_sdb.add(frozenset([sdb0, sdb1]))
            matches.append((r + 1, 'XD', (sm_mx, sw), (sdb0, sdb1)))

        # Track who has been in special court for rotation visibility
        for m in spec_m:
            special_count[m] = special_count.get(m, 0) + 1
        for w in spec_w:
            special_count[w] = special_count.get(w, 0) + 1

        # Available players for standard courts
        avail_m = [p for p in range(M) if p not in spec_m]
        avail_w = [p for p in range(W) if p not in spec_w]

        # ---- DB assignment ----
        if need_db > 0:
            cand = sorted(avail_m, key=lambda p: -db_left[p])
            if len(cand) < need_db:
                return None
            chosen = set(cand[:need_db])
            for p in chosen:
                db_left[p] -= 1

            # Skip round-robin when special court is active (players removed may break evenness)
            if is_uniform and not special and need_db == M - len(spec_m) and need_db == len(avail_m):
                # Use round-robin when all available men are in DB
                rr_idx = r % len(rr_db)
                rr_round = rr_db[rr_idx]
                # Filter to only available men
                valid_pairs = [p for p in rr_round if all(pi in avail_m for pi in p)]
                if len(valid_pairs) >= 2:
                    pp = list(valid_pairs)
                    random.shuffle(pp)
                    for k in range(0, len(pp), 2):
                        t1, t2 = pp[k], pp[k + 1]
                        used_db.add(frozenset(t1))
                        used_db.add(frozenset(t2))
                        matches.append((r + 1, 'DB', t1, t2))
                else:
                    pp = flex_pair(list(chosen), used_db)
                    if not pp:
                        return None
                    for t1, t2 in pp:
                        matches.append((r + 1, 'DB', t1, t2))
            else:
                pp = flex_pair(list(chosen), used_db)
                if not pp:
                    return None
                for t1, t2 in pp:
                    matches.append((r + 1, 'DB', t1, t2))

            # Update available men for MX
            avail_m = [p for p in avail_m if p not in chosen]

        # ---- WB assignment ----
        if need_wb > 0:
            cand = sorted(avail_w, key=lambda p: -wb_left[p])
            if len(cand) < need_wb:
                return None
            chosen = set(cand[:need_wb])
            for p in chosen:
                wb_left[p] -= 1

            if is_uniform and not special and need_wb == W - len(spec_w) and need_wb == len(avail_w):
                rr_idx = r % len(rr_wb)
                rr_round = rr_wb[rr_idx]
                valid_pairs = [p for p in rr_round if all(pi in avail_w for pi in p)]
                if len(valid_pairs) >= 2:
                    pp = list(valid_pairs)
                    random.shuffle(pp)
                    for k in range(0, len(pp), 2):
                        t1, t2 = pp[k], pp[k + 1]
                        used_wb.add(frozenset(t1))
                        used_wb.add(frozenset(t2))
                        matches.append((r + 1, 'WB', t1, t2))
                else:
                    pp = flex_pair(list(chosen), used_wb)
                    if not pp:
                        return None
                    for t1, t2 in pp:
                        matches.append((r + 1, 'WB', t1, t2))
            else:
                pp = flex_pair(list(chosen), used_wb)
                if not pp:
                    return None
                for t1, t2 in pp:
                    matches.append((r + 1, 'WB', t1, t2))

            avail_w = [p for p in avail_w if p not in chosen]

        # ---- MX assignment (standard) ----
        if need_mx > 0:
            mx_m = list(avail_m)
            mx_f = list(avail_w)
            if len(mx_m) != len(mx_f) or len(mx_m) < 2:
                return None
            pp = flex_mix(mx_m, mx_f, used_mx)
            if not pp:
                return None
            for t1, t2 in pp:
                matches.append((r + 1, 'MX', t1, t2))

    # ---- Verification ----
    mc = {p: 0 for p in range(M)}
    fc = {p: 0 for p in range(W)}
    for m_entry in matches:
        typ = m_entry[1]
        t1, t2 = m_entry[2], m_entry[3]
        if typ == 'DB':
            for p in t1 + t2:
                mc[p] += 1
        elif typ == 'WB':
            for p in t1 + t2:
                fc[p] += 1
        elif typ == 'MX':
            m1, w1 = t1
            m2, w2 = t2
            mc[m1] += 1
            mc[m2] += 1
            fc[w1] += 1
            fc[w2] += 1
        elif typ == 'XW':
            # MXxWB: (man, woman_mx) vs (woman0, woman1)
            m, w_mx = t1
            w0, w1 = t2
            mc[m] += 1
            fc[w_mx] += 1
            fc[w0] += 1
            fc[w1] += 1
        elif typ == 'XD':
            # MXxDB: (man_mx, woman) vs (man0, man1)
            m_mx, w = t1
            m0, m1 = t2
            mc[m_mx] += 1
            mc[m0] += 1
            mc[m1] += 1
            fc[w] += 1

    if not (all(v == N for v in mc.values()) and all(v == N for v in fc.values())):
        return None

    if not _cp(matches):
        return None

    return matches  # Return raw matches for gen() to format + compare


def _cp(matches):
    """Check pair uniqueness across all matches.
    For special courts (XW/XD), allows repeats when unique combos are exhausted.
    """
    dbp = set()
    wbp = set()
    mxp = set()
    # Special court tracking: use counters, allow repeats beyond unique limit
    xwp_count = {}  # (man,woman) -> count
    xwwp_count = {}  # frozenset(2 women) -> count
    xdp_count = {}  # (man,woman) -> count
    xddp_count = {}  # frozenset(2 men) -> count
    MAX_SPECIAL_REPEAT = 2  # Allow up to 2 repeats for special court

    for m_entry in matches:
        typ = m_entry[1]
        t1, t2 = m_entry[2], m_entry[3]
        if typ == 'DB':
            if frozenset(t1) in dbp or frozenset(t2) in dbp:
                return False
            dbp.add(frozenset(t1))
            dbp.add(frozenset(t2))
        elif typ == 'WB':
            if frozenset(t1) in wbp or frozenset(t2) in wbp:
                return False
            wbp.add(frozenset(t1))
            wbp.add(frozenset(t2))
        elif typ == 'MX':
            if t1 in mxp or t2 in mxp:
                return False
            mxp.add(t1)
            mxp.add(t2)
        elif typ == 'XW':
            # MXxWB: t1=(man,woman_mx), t2=(woman0,woman1)
            xwp_count[t1] = xwp_count.get(t1, 0) + 1
            if xwp_count[t1] > MAX_SPECIAL_REPEAT:
                return False
            wb_pair = frozenset(t2)
            xwwp_count[wb_pair] = xwwp_count.get(wb_pair, 0) + 1
            if xwwp_count[wb_pair] > MAX_SPECIAL_REPEAT:
                return False
        elif typ == 'XD':
            # MXxDB: t1=(man_mx,woman), t2=(man0,man1)
            xdp_count[t1] = xdp_count.get(t1, 0) + 1
            if xdp_count[t1] > MAX_SPECIAL_REPEAT:
                return False
            db_pair = frozenset(t2)
            xddp_count[db_pair] = xddp_count.get(db_pair, 0) + 1
            if xddp_count[db_pair] > MAX_SPECIAL_REPEAT:
                return False

    return True


def _fmt(matches, M, W, N=5):
    mn = [f'M{i + 1}' for i in range(M)]
    wn = [f'W{i + 1}' for i in range(W)]
    lines = [f'===== {M}男{W}女 双打排阵（{N}轮）=====\n']

    for rnd in range(1, N + 1):
        rm = [m for m in matches if m[0] == rnd]
        a = sum(1 for m in rm if m[1] == 'DB')
        b = sum(1 for m in rm if m[1] == 'WB')
        c = sum(1 for m in rm if m[1] == 'MX')
        sx = sum(1 for m in rm if m[1] in ('XW', 'XD'))
        label = f'{a}男双+{b}女双+{c}混双'
        if sx > 0:
            label += '+' + '+'.join('MX×WB' if m[1] == 'XW' else 'MX×DB' for m in rm if m[1] in ('XW', 'XD'))
        lines.append(f'--- 第{rnd}轮 ({label}) ---')

        for m_entry in rm:
            typ = m_entry[1]
            t1, t2 = m_entry[2], m_entry[3]
            if typ == 'DB':
                lines.append(f'  [DB] {"+".join(mn[i] for i in t1)} vs {"+".join(mn[i] for i in t2)}')
            elif typ == 'WB':
                lines.append(f'  [WB] {"+".join(wn[i] for i in t1)} vs {"+".join(wn[i] for i in t2)}')
            elif typ == 'MX':
                lines.append(f'  [MX] {mn[t1[0]]}+{wn[t1[1]]} vs {mn[t2[0]]}+{wn[t2[1]]}')
            elif typ == 'XW':
                # MXxWB: (man, woman_mx) vs (woman0, woman1)
                lines.append(f'  [MX×WB] {mn[t1[0]]}+{wn[t1[1]]} vs {wn[t2[0]]}+{wn[t2[1]]}')
            elif typ == 'XD':
                # MXxDB: (man_mx, woman) vs (man0, man1)
                lines.append(f'  [MX×DB] {mn[t1[0]]}+{wn[t1[1]]} vs {mn[t2[0]]}+{mn[t2[1]]}')

        lines.append('')

    # Verification summary
    lines.append('--- 验证 ---')
    lines.append('零重复搭档 | 每人N场')
    vm = {tuple(sorted([a, b])): 0 for a, b in combinations(range(M), 2)}
    vf = {tuple(sorted([a, b])): 0 for a, b in combinations(range(W), 2)}

    for m_entry in matches:
        typ = m_entry[1]
        t1, t2 = m_entry[2], m_entry[3]
        if typ == 'DB':
            for a in t1:
                for b in t2:
                    vm[tuple(sorted([a, b]))] += 1
        elif typ == 'WB':
            for a in t1:
                for b in t2:
                    vf[tuple(sorted([a, b]))] += 1
        elif typ == 'MX':
            m1, w1 = t1
            m2, w2 = t2
            vm[tuple(sorted([m1, m2]))] += 1
            vf[tuple(sorted([w1, w2]))] += 1
        elif typ == 'XW':
            # MXxWB: t1 has (man, woman_mx), t2 has (woman0, woman1)
            # No MvsM, only WvsW from the WB side
            w0, w1 = t2
            vf[tuple(sorted([w0, w1]))] += 1
        elif typ == 'XD':
            # MXxDB: t1 has (man_mx, woman), t2 has (man0, man1)
            m0, m1 = t2
            vm[tuple(sorted([m0, m1]))] += 1

    mr = sum(1 for v in vm.values() if v > 0)
    fr = sum(1 for v in vf.values() if v > 0)
    mm = [f'{mn[a]}vs{mn[b]}' for (a, b), v in vm.items() if v == 0]
    mf = [f'{wn[a]}vs{wn[b]}' for (a, b), v in vf.items() if v == 0]
    lines.append(f'[对阵] 男{mr}/{len(vm)}{" 全对阵!" if not mm else " 缺"+str(len(mm))+"组"}')
    lines.append(f'[对阵] 女{fr}/{len(vf)}{" 全对阵!" if not mf else " 缺"+str(len(mf))+"组"}')

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    if '--test' in sys.argv:
        tests = [(4, 4), (6, 6), (8, 8), (10, 10), (10, 6), (8, 4), (12, 12)]
        for M, W in tests:
            if (M + W) % 4 != 0:
                continue
            print(f'\n{"=" * 60}')
            print(gen(M, W))

    elif '--special-test' in sys.argv:
        tests = [(1, 3), (3, 1), (3, 5), (5, 3), (1, 7), (7, 1), (5, 7), (7, 5), (9, 7), (7, 9)]
        for M, W in tests:
            if (M + W) % 4 != 0:
                continue
            print(f'\n{"=" * 60}')
            print(gen(M, W))

    elif '--rounds' in sys.argv:
        mi = sys.argv.index('--men') if '--men' in sys.argv else -1
        wi = sys.argv.index('--women') if '--women' in sys.argv else -1
        ri = sys.argv.index('--rounds') if '--rounds' in sys.argv else -1
        M = int(sys.argv[mi + 1]) if mi >= 0 else 8
        W = int(sys.argv[wi + 1]) if wi >= 0 else 8
        N = int(sys.argv[ri + 1]) if ri >= 0 else 5
        print(gen(M, W, N))

    elif len(sys.argv) >= 5:
        print(gen(int(sys.argv[2]), int(sys.argv[4])))

    else:
        print('Usage: python tennis_scheduler.py --men N --women N [--rounds N]')
        print('       python tennis_scheduler.py --test')
        print('       python tennis_scheduler.py --special-test')
