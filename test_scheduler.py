#!/usr/bin/env python3
"""
Test suite for tennis_scheduler.py
Tests various configurations and outputs a detailed report.
"""

import sys, time, re
from collections import defaultdict

sys.path.insert(0, r'E:\Tennis_tools')
from tennis_scheduler import gen, _opponent_stats

REPORT_LINES = []

def log(msg=""):
    REPORT_LINES.append(msg)
    print(msg)

def parse_matches(text, M, W):
    """Parse formatted gen() output back into raw match tuples."""
    matches = []
    current_round = 0
    for line in text.strip().split('\n'):
        if line.startswith('--- 第'):
            m = re.match(r'--- 第(\d+)轮', line)
            if m: current_round = int(m.group(1))
        elif '[DB]' in line:
            m = re.match(r'\s+\[DB\] (\w+)\+(\w+) vs (\w+)\+(\w+)', line)
            if m:
                t1 = (int(m.group(1)[1:])-1, int(m.group(2)[1:])-1)
                t2 = (int(m.group(3)[1:])-1, int(m.group(4)[1:])-1)
                matches.append((current_round, 'DB', t1, t2))
        elif '[WB]' in line:
            m = re.match(r'\s+\[WB\] (\w+)\+(\w+) vs (\w+)\+(\w+)', line)
            if m:
                t1 = (int(m.group(1)[1:])-1, int(m.group(2)[1:])-1)
                t2 = (int(m.group(3)[1:])-1, int(m.group(4)[1:])-1)
                matches.append((current_round, 'WB', t1, t2))
        elif '[MX]' in line and '[MX×' not in line:
            m = re.match(r'\s+\[MX\] (\w+)\+(\w+) vs (\w+)\+(\w+)', line)
            if m:
                t1 = (int(m.group(1)[1:])-1, int(m.group(2)[1:])-1)
                t2 = (int(m.group(3)[1:])-1, int(m.group(4)[1:])-1)
                matches.append((current_round, 'MX', t1, t2))
        elif '[MX×WB]' in line:
            m = re.match(r'\s+\[MX×WB\] (\w+)\+(\w+) vs (\w+)\+(\w+)', line)
            if m:
                t1 = (int(m.group(1)[1:])-1, int(m.group(2)[1:])-1)
                t2 = (int(m.group(3)[1:])-1, int(m.group(4)[1:])-1)
                matches.append((current_round, 'XW', t1, t2))
        elif '[MX×DB]' in line:
            m = re.match(r'\s+\[MX×DB\] (\w+)\+(\w+) vs (\w+)\+(\w+)', line)
            if m:
                t1 = (int(m.group(1)[1:])-1, int(m.group(2)[1:])-1)
                t2 = (int(m.group(3)[1:])-1, int(m.group(4)[1:])-1)
                matches.append((current_round, 'XD', t1, t2))
    return matches

def analyze_matches(matches, M, W, N):
    """Analyze match tuples and return statistics dict."""
    partner_cnt = defaultdict(int)
    opp_cnt = defaultdict(int)
    player_rounds = defaultdict(set)
    player_partners = defaultdict(set)
    round_types = defaultdict(lambda: defaultdict(int))

    for rnd, typ, t1, t2 in matches:
        round_types[rnd][typ] += 1
        for pid in t1 + t2:
            player_rounds[pid].add(rnd)
        # Partner
        for a, b in [(t1[0], t1[1]), (t2[0], t2[1])]:
            k = tuple(sorted([a, b]))
            partner_cnt[k] += 1
            player_partners[a].add(b)
            player_partners[b].add(a)
        # Opponent
        for a in t1:
            for b in t2:
                k = tuple(sorted([a, b]))
                opp_cnt[k] += 1

    rpp = {p: len(rs) for p, rs in player_rounds.items()}
    mp = max(partner_cnt.values()) if partner_cnt else 0
    mxo, o3 = _opponent_stats(matches)
    o3p = {k: v for k, v in opp_cnt.items() if v >= 3}

    return {
        'total_matches': len(matches),
        'max_partner_repeat': mp,
        'max_opp_repeat': mxo,
        'over3_count': o3,
        'over3_opponents': o3p,
        'min_rounds': min(rpp.values()) if rpp else 0,
        'max_rounds': max(rpp.values()) if rpp else 0,
        'player_partners': {k: len(v) for k, v in player_partners.items()},
        'round_types': {k: dict(v) for k, v in round_types.items()},
    }

def run_test(name, M, W, N=5):
    log(f"\n{'='*60}")
    log(f"  TEST: {name}  ({M}M, {W}W, {N}轮)")
    log(f"{'='*60}")

    t0 = time.time()
    result = gen(M, W, N)
    elapsed = time.time() - t0
    log(f"  ⏱  {elapsed:.2f}s")

    if 'Warning' in result or 'Error' in result:
        log(f"  ❌ FAILED: {result[:80]}")
        return None, elapsed

    matches = parse_matches(result, M, W)
    if not matches:
        log(f"  ❌ FAILED: Could not parse matches")
        return None, elapsed

    st = analyze_matches(matches, M, W, N)
    log(f"  场次: {st['total_matches']}")
    log(f"  搭档最大重复: {st['max_partner_repeat']}")
    log(f"  对手最大重复: {st['max_opp_repeat']}")
    log(f"  对手≥3次: {st['over3_count']}")
    log(f"  每人轮次均匀: {st['min_rounds']}-{st['max_rounds']}")

    issues = []
    if st['max_partner_repeat'] > 1:
        issues.append(f"  ⚠️ 搭档重复 (max={st['max_partner_repeat']})")
    if st['over3_count'] > 0:
        issues.append(f"  ⚠️ 对手≥3次: {st['over3_count']}对 (最差={st['max_opp_repeat']})")
        top5 = sorted(st['over3_opponents'].items(), key=lambda x: -x[1])[:5]
        for pair, cnt in top5:
            issues.append(f"       {pair} x{cnt}")
    if st['min_rounds'] != st['max_rounds']:
        issues.append(f"  ❌ 每人轮次不均: {st['min_rounds']}-{st['max_rounds']}")

    # Partner diversity
    divs = list(st['player_partners'].values())
    log(f"  搭档多样性: avg={sum(divs)/len(divs):.1f} range={min(divs)}-{max(divs)}")

    # Round breakdown
    parts = []
    for r in sorted(st['round_types'].keys()):
        t = ' '.join(f"{t}{c}" for t,c in sorted(st['round_types'][r].items()))
        parts.append(f"R{r}:{t}")
    log(f"  轮次组成: {'  '.join(parts[:3])}")

    if issues:
        for issue in issues:
            log(issue)
        return st, elapsed

    log(f"  ✅ OK")
    return st, elapsed

def generate_report():
    log("=" * 60)
    log("  网球排阵算法测试报告")
    log(f"  测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)

    results = []

    log("\n## 1. 标准对称配置")
    for name, M, W, N in [
        ("4M4W", 4, 4, 5), ("6M6W", 6, 6, 5),
        ("8M8W", 8, 8, 5), ("10M10W", 10, 10, 5),
        ("12M12W", 12, 12, 5),
    ]:
        if (M+W)%4==0:
            s, e = run_test(name, M, W, N) or (None, 0)
            results.append((name, M, W, N, s, e))

    log("\n## 2. 男女混合配置")
    for name, M, W, N in [
        ("8M4W", 8, 4, 5), ("10M6W", 10, 6, 5),
        ("6M10W", 6, 10, 5), ("8M12W", 8, 12, 5),
        ("12M8W", 12, 8, 5),
    ]:
        if (M+W)%4==0:
            s, e = run_test(name, M, W, N) or (None, 0)
            results.append((name, M, W, N, s, e))

    log("\n## 3. 轮次自定义")
    for name, M, W, N in [
        ("8M8W 3轮", 8, 8, 3), ("8M8W 4轮", 8, 8, 4),
        ("8M8W 6轮", 8, 8, 6),
    ]:
        if (M+W)%4==0:
            s, e = run_test(name, M, W, N) or (None, 0)
            results.append((name, M, W, N, s, e))

    log("\n" + "=" * 60)
    log("  汇总表")
    log("=" * 60)
    log(f"{'配置':<16} {'耗时':<6} {'max对手':<8} {'≥3对手':<8} {'max搭档':<8}")
    log("-" * 50)
    for name, _, _, _, st, el in results:
        if st:
            log(f"{name:<16} {el:<6.2f} {st['max_opp_repeat']:<8} {st['over3_count']:<8} {st['max_partner_repeat']:<8}")
        else:
            log(f"{name:<16} {el:<6.2f} {'❌':<8} {'❌':<8} {'❌':<8}")

    path = r'E:\Tennis_tools\test_report.txt'
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(REPORT_LINES))
    log(f"\n📄 {path}")

if __name__ == '__main__':
    generate_report()
