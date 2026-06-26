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


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def gen(M, W, N=5, tries=3000):
    if (M, W) in PRESETS and N == 5:
        return _fmt(PRESETS[(M, W)], M, W, N)
    dist = construct_dist(M, W, N)
    if not dist:
        return f"Error: no feasible dist (M={M},W={W},N={N})"
    is_uniform = all(d == dist[0] for d in dist)

    for _ in range(tries):
        r = _go(M, W, dist, is_uniform, N)
        if r:
            return r
    return f"Warning: no schedule (M={M},W={W}) after {tries} tries"


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

    return _fmt(matches, M, W, N)


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
