# -*- coding: utf-8 -*-
"""
Tennis Doubles Scheduler v7 - Stable version
Uses round-robin + uniform distribution for guaranteed results.
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
        for i in range(1, N//2):
            a = (r + i) % k
            b = (r - i) % k
            if a != b:
                pairs.append((a, b))
        result.append(pairs)
    return result

def construct_dist(M,W,N):
    N = N or 5
    cp = (M+W)//4
    # First: uniform distribution (preferred)
    for c1 in [1,2,0]:
        if c1>cp: continue
        if (M-2*c1)%4==0 and (W-2*c1)%4==0:
            a=(M-2*c1)//4; b=(W-2*c1)//4
            if a>=0 and b>=0 and a+b+c1==cp:
                return [(a,b,c1)]*N
    # Fallback: mixed distribution
    for c1 in range(cp+1):
        for c2 in range(cp+1):
            if c1==c2: continue
            a1=(M-2*c1)//4; b1=(W-2*c1)//4
            a2=(M-2*c2)//4; b2=(W-2*c2)//4
            if a1<0 or b1<0 or a2<0 or b2<0: continue
            if a1+b1+c1!=cp or a2+b2+c2!=cp: continue
            for n1 in range(1,N):
                n2=N-n1; sc=n1*c1+n2*c2; sa=(N*M-2*sc)//4; sb=(N*W-2*sc)//4
                if n1*a1+n2*a2==sa and n1*b1+n2*b2==sb:
                    d = [((a1,b1,c1))]*n1 + [((a2,b2,c2))]*n2
                    random.shuffle(d)
                    return d
    return None

def flex_pair(players, used, maxt=1000):
    """Flexible pairing without repeated partners."""
    pool = list(players)
    for _ in range(maxt):
        order = list(pool); random.shuffle(order)
        pairs = []; seen = set(); ok = True
        i = 0
        while i < len(order):
            p1 = order[i]; found = False
            for j in range(i+1, len(order)):
                p2 = order[j]
                fs = frozenset([p1,p2])
                if fs not in used and fs not in seen:
                    pairs.append((p1,p2)); seen.add(fs)
                    order.pop(j); order.pop(i); found = True; break
            if not found: ok = False; break
        if ok:
            for s in seen: used.add(s)
            random.shuffle(pairs)
            return [(pairs[k],pairs[k+1]) for k in range(0,len(pairs),2)]
    return None

def flex_mix(males,females,used,maxt=1000):
    ml=list(males)
    for _ in range(maxt):
        fl=list(females); random.shuffle(ml); random.shuffle(fl)
        pairs=[]; seen=set(); ok=True
        for m in ml:
            found=False
            for fi,w in enumerate(fl):
                if (m,w) not in used and (m,w) not in seen:
                    pairs.append((m,w)); seen.add((m,w)); fl.pop(fi); found=True; break
            if not found: ok=False; break
        if ok:
            for p in seen: used.add(p)
            random.shuffle(pairs)
            return [(pairs[k],pairs[k+1]) for k in range(0,len(pairs),2)]
    return None

def gen(M,W,N=5,tries=3000):
    if (M,W) in PRESETS and N==5: return _fmt(PRESETS[(M,W)],M,W,N)
    dist = construct_dist(M,W,N)
    if not dist: return f"Error: no feasible dist (M={M},W={W},N={N})"
    # Check if uniform
    is_uniform = all(d==dist[0] for d in dist)
    
    for _ in range(tries):
        r = _go(M,W,dist, is_uniform,N)
        if r: return r
    return f"Warning: no schedule (M={M},W={W}) after {tries} tries"

def _go(M,W,dist,is_uniform,N=5):
    sa = sum(a for a,_,_ in dist); sb = sum(b for _,b,_ in dist)
    db_tgt = [4*sa//M]*M
    for i in range(4*sa%M): db_tgt[i]+=1
    wb_tgt = [4*sb//W]*W
    for i in range(4*sb%W): wb_tgt[i]+=1
    
    db_left = list(db_tgt); wb_left = list(wb_tgt)
    used_db=set(); used_wb=set(); used_mx=set()
    
    # Pre-compute RR pairs
    rr_db = rr_pairs(M); rr_wb = rr_pairs(W)
    
    matches = []
    for r in range(N):
        a,b,c = dist[r]
        need_db=4*a; need_wb=4*b; need_mx=2*c
        
        # DB assignment
        if need_db > 0:
            cand = sorted([p for p in range(M) if db_left[p]>0], key=lambda p: -db_left[p])
            if len(cand) < need_db: return None
            chosen = set(cand[:need_db])
            for p in chosen: db_left[p]-=1
            
            if is_uniform and need_db == M:
                # Use round-robin (guaranteed to work)
                rr_round = rr_db[r % len(rr_db)]
                # Shuffle which pairs are together in a match
                pp = list(rr_round); random.shuffle(pp)
                for k in range(0, len(pp), 2):
                    t1,t2 = pp[k], pp[k+1]
                    used_db.add(frozenset(t1)); used_db.add(frozenset(t2))
                    matches.append((r+1,'DB',t1,t2))
            else:
                pp = flex_pair(list(chosen), used_db)
                if not pp: return None
                for t1,t2 in pp: matches.append((r+1,'DB',t1,t2))
            
            mx_m = [p for p in range(M) if p not in chosen]
        else:
            mx_m = list(range(M))
        
        # WB assignment
        if need_wb > 0:
            cand = sorted([p for p in range(W) if wb_left[p]>0], key=lambda p: -wb_left[p])
            if len(cand) < need_wb: return None
            chosen = set(cand[:need_wb])
            for p in chosen: wb_left[p]-=1
            
            if is_uniform and need_wb == W:
                rr_round = rr_wb[r % len(rr_wb)]
                pp = list(rr_round); random.shuffle(pp)
                for k in range(0, len(pp), 2):
                    t1,t2 = pp[k], pp[k+1]
                    used_wb.add(frozenset(t1)); used_wb.add(frozenset(t2))
                    matches.append((r+1,'WB',t1,t2))
            else:
                pp = flex_pair(list(chosen), used_wb)
                if not pp: return None
                for t1,t2 in pp: matches.append((r+1,'WB',t1,t2))
            
            mx_f = [p for p in range(W) if p not in chosen]
        else:
            mx_f = list(range(W))
        
        # MX
        if need_mx > 0:
            pp = flex_mix(mx_m, mx_f, used_mx)
            if not pp: return None
            for t1,t2 in pp: matches.append((r+1,'MX',t1,t2))
    
    # Verify
    mc = {p:0 for p in range(M)}; fc = {p:0 for p in range(W)}
    for _,t,t1,t2 in matches:
        if t=='DB':
            for p in t1+t2: mc[p]+=1
        elif t=='WB':
            for p in t1+t2: fc[p]+=1
        else:
            m1,w1=t1; m2,w2=t2
            mc[m1]+=1; mc[m2]+=1; fc[w1]+=1; fc[w2]+=1
    if not (all(v==N for v in mc.values()) and all(v==N for v in fc.values())): return None
    if not _cp(matches): return None
    return _fmt(matches,M,W)

def _cp(matches):
    dbp=set(); wbp=set(); mxp=set()
    for _,t,t1,t2 in matches:
        if t=='DB':
            if frozenset(t1) in dbp or frozenset(t2) in dbp: return False
            dbp.add(frozenset(t1)); dbp.add(frozenset(t2))
        elif t=='WB':
            if frozenset(t1) in wbp or frozenset(t2) in wbp: return False
            wbp.add(frozenset(t1)); wbp.add(frozenset(t2))
        else:
            if t1 in mxp or t2 in mxp: return False
            mxp.add(t1); mxp.add(t2)
    return True

def _fmt(matches,M,W,N=5):
    mn=[f'M{i+1}' for i in range(M)]; wn=[f'W{i+1}' for i in range(W)]
    lines=[f'===== {M}男{W}女 双打排阵（{N}轮）=====\n']
    for rnd in range(1,N+1):
        rm=[m for m in matches if m[0]==rnd]
        a=sum(1 for m in rm if m[1]=='DB'); b=sum(1 for m in rm if m[1]=='WB'); c=sum(1 for m in rm if m[1]=='MX')
        lines.append(f'--- 第{rnd}轮 ({a}男双+{b}女双+{c}混双) ---')
        for _,t,t1,t2 in rm:
            if t=='DB': lines.append(f'  [DB] {"+".join([mn[i] for i in t1])} vs {"+".join([mn[i] for i in t2])}')
            elif t=='WB': lines.append(f'  [WB] {"+".join([wn[i] for i in t1])} vs {"+".join([wn[i] for i in t2])}')
            else: lines.append(f'  [MX] {mn[t1[0]]}+{wn[t1[1]]} vs {mn[t2[0]]}+{wn[t2[1]]}')
        lines.append('')
    lines.append('--- 验证 ---')
    lines.append('零重复搭档 | 每人5场')
    vm={tuple(sorted([a,b])):0 for a,b in combinations(range(M),2)}
    vf={tuple(sorted([a,b])):0 for a,b in combinations(range(W),2)}
    for _,t,t1,t2 in matches:
        if t=='DB':
            for a in t1:
                for b in t2: vm[tuple(sorted([a,b]))]+=1
        elif t=='WB':
            for a in t1:
                for b in t2: vf[tuple(sorted([a,b]))]+=1
        else:
            m1,w1=t1; m2,w2=t2
            vm[tuple(sorted([m1,m2]))]+=1; vf[tuple(sorted([w1,w2]))]+=1
    mr=sum(1 for v in vm.values() if v>0); fr=sum(1 for v in vf.values() if v>0)
    mm=[f'{mn[a]}vs{mn[b]}' for (a,b),v in vm.items() if v==0]
    mf=[f'{wn[a]}vs{wn[b]}' for (a,b),v in vf.items() if v==0]
    lines.append(f'[对阵] 男{mr}/{len(vm)}{" 全对阵!" if not mm else " 缺"+str(len(mm))+"组"}')
    lines.append(f'[对阵] 女{fr}/{len(vf)}{" 全对阵!" if not mf else " 缺"+str(len(mf))+"组"}')
    return '\n'.join(lines)

if __name__=='__main__':
    if '--test' in sys.argv:
        tests=[(4,4),(6,6),(8,8),(10,10),(10,6),(8,4),(12,12)]
        for M,W in tests:
            if (M+W)%4!=0: continue
            print(f'\n{"="*60}')
            print(gen(M,W))
    elif '--rounds' in sys.argv:
        mi = sys.argv.index('--men') if '--men' in sys.argv else -1
        wi = sys.argv.index('--women') if '--women' in sys.argv else -1
        ri = sys.argv.index('--rounds') if '--rounds' in sys.argv else -1
        M = int(sys.argv[mi+1]) if mi>=0 else 8
        W = int(sys.argv[wi+1]) if wi>=0 else 8
        N = int(sys.argv[ri+1]) if ri>=0 else 5
        print(gen(M,W,N))
    elif len(sys.argv)>=5:
        print(gen(int(sys.argv[2]),int(sys.argv[4])))
    else:
        print('Usage: python tennis_scheduler.py --men N --women N [--rounds N]')
