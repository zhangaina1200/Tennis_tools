# Plan B — 步进式重构方案（第1步 + 第2步）

> 基于娜姐的三步路线，先做第1步（对手感知补齐）+ 第2步（统一分组引擎）
> 基于现有 `go_exact` / `enumerate_pairings` / `hungarian` 等已有函数进行改造

---

## 总览

```
Plan B = 第1步（对手感知补齐）+ 第2步（统一分组引擎）

第3步（全局轮次规划器/rrPairs 矩阵）后续再做
```

---

# 第1步：MX 配对时的对手感知

## 1.1 现状问题

当前代码的 `opp_counters` 只在以下位置有记录：

| 位置 | DB | WB | MX | XW/XD |
|------|:--:|:--:|:--:|:-----:|
| `enumerate_pairings` 内检查对手 | ✅ | ✅ | — | — |
| `go_exact` 内 `_add_opp` 写入 | ✅ | ✅ | ✅ | ❌ |
| `build_cost_matrix` 内对手感知 | — | — | ❌ | — |

**缺失点：**
1. `build_cost_matrix`（Python） / `buildCostMatrix`（JS） 没有考虑 `oppCounters`，匈牙利选配对时完全无视了对手上限
2. XW/XD 特殊场地不记录对手关系，也不检查对手上限

## 1.2 buildCostMatrix 增加 oppCounters 检查

### 思路

MX 的代价矩阵中，每个格子 `(m_i, w_j)` 表示"该轮让 m_i 和 w_j 搭档"的成本。当前只考虑了水平差 + 搭档重复。**需要增加对手感知成本**。

对手关系在中场配对确定后自然形成：
```
配对: (m1, w1) vs (m2, w2)
对手: m1↔m2, w1↔w2
```

对每个 `(m_i, w_j)` 的代价增加项：

```
oppPenalty(m_i, w_j) = 
  Σ (对于可能和 m_i 对位的其他男选手 m_k)
    如果 oppCounters[m_i, m_k] ≥ 3 → INF（硬禁止）
    否则 oppCounters[m_i, m_k] * 100（软惩罚）

  类似地考虑 w_j 和其他女选手的对位
```

但问题在于：**匈牙利在构建 costMatrix 时还不知道哪个 m 和哪个 w 会对位**。完整配对由匈牙利决定。

### 实现方案：双阶段

#### 阶段 A — costMatrix 中的预感知（软约束）

在 `build_cost_matrix` 中，对每个 `(man_idx, woman_idx)` 计算：

```python
def build_cost_matrix(men, women, used_mx_pairs, male_levels, female_levels, opp_counters=None):
    m = len(men)
    matrix = []
    for mi in range(m):
        row = []
        man_idx = men[mi]
        for wi in range(w):
            woman_idx = women[wi]
            cost = abs((male_levels[man_idx] if ... else 3.0)
                       - (female_levels[woman_idx] if ... else 3.0))
            
            # —— 搭档重复惩罚（已有）——
            pair_key = str(man_idx) + ',M' + str(woman_idx)
            if used_mx_pairs and pair_key in used_mx_pairs:
                cost += INF / 2  # 硬禁止
            
            # —— 对手感知（新增）——
            if opp_counters:
                # 男性对手成本：man_idx vs 其他在配对的男选手
                for other_m in men:
                    if other_m == man_idx: continue
                    m_key = 'M' + str(min(man_idx, other_m)) + ',M' + str(max(man_idx, other_m))
                    cnt = opp_counters.get(m_key, 0)
                    if cnt >= 3:
                        cost += INF / 2  # 选了此配对可能导致对手超限
                    elif cnt > 0:
                        cost += cnt * 200  # 软惩罚
                
                # 女性对手成本：woman_idx vs 其他在配对的女士
                for other_w in women:
                    if other_w == woman_idx: continue
                    w_key = 'W' + str(min(woman_idx, other_w)) + ',W' + str(max(woman_idx, other_w))
                    cnt = opp_counters.get(w_key, 0)
                    if cnt >= 3:
                        cost += INF / 2
                    elif cnt > 0:
                        cost += cnt * 200
            
            row.append(cost)
        matrix.append(row)
    return matrix
```

**说明**：预感知不是精确的——它会对所有可能的对手对都加惩罚，而不是只对最终实际的对手对。但这样匈牙利会倾向于选"对手关系历史较少"的配对方案。

#### 阶段 B — 匈牙利结果后验证（硬约束）

匈牙利返回 assignment 后，在 `go_exact` 的 MX 组装阶段，在把配对组装成 `(m1,w1) vs (m2,w2)` 之前/之后，**硬性检查 opponent 上限**：

```python
# 在 go_exact 中，组装 MX 比赛后：
for ci in range(c):
    m1 = mx_men[2*ci]; w1 = mx_women[assign[2*ci]]
    m2 = mx_men[2*ci+1]; w2 = mx_women[assign[2*ci+1]]
    
    m_opp_key = 'M' + str(min(m1, m2)) + ',M' + str(max(m1, m2))
    w_opp_key = 'W' + str(min(w1, w2)) + ',W' + str(max(w1, w2))
    
    if opp_counters.get(m_opp_key, 0) >= 3:
        return None  # 硬拒绝，回退到下一个分布
    if opp_counters.get(w_opp_key, 0) >= 3:
        return None
```

### 代码改动清单（Python）

| 文件 | 函数 | 改动 |
|------|------|------|
| `tennis_scheduler.py` | `build_cost_matrix()` | 增加 `opp_counters` 参数，增加对手成本计算 |
| `tennis_scheduler.py` | `go_exact()` MX 段 | 调用 build_cost_matrix 时传入 opp_counters |
| `tennis_scheduler.py` | `go_exact()` MX 段 | 组装 match 后硬性检查 opp 上限 |

### 代码改动清单（JS）

| 文件 | 函数 | 改动 |
|------|------|------|
| `index.html` | `buildCostMatrix()` | 增加 `oppCounters` 参数，对手成本计算 |
| `index.html` | `go_exact()` MX 段 | 调用和验证同步修改 |

---

## 1.3 XW/XD 补上对手记录

### 现状

`_pick_xw` / `_pick_xd` 只关注搭档不重复（used_smx / used_swb / used_sdb），**完全不关心对手关系**，也不向 `opp_counters` 写入记录。

### 实现

在 `go_exact` 中，特殊场地 match 组装后，**追加对手记录**：

#### XW（MX×WB）的对手关系

```
赛场: (男A + 女B) vs (女C + 女D)
对手对:
  - 男A vs 女C（跨性别，不需要）→ 忽略
  - 男A vs 女D（跨性别，不需要）→ 忽略  
  - 女B vs 女C（同性：WB 侧对手）→ 'W' + min(B,C) + ',W' + max(B,C)
  - 女B vs 女D（同性：WB 侧对手）→ 'W' + min(B,D) + ',W' + max(B,D)
```

**修正**：网球双打的对手只算同性（男对男，女对女），跨性别的不用算。所以：

```
XW 场景:
  女B(混双侧女) vs 女C(WB侧) → 女双对手
  女B(混双侧女) vs 女D(WB侧) → 女双对手
  男A 在本场没有男性对手对位 → 不计
```

#### XD（MX×DB）的对手关系

```
赛场: (男A + 女B) vs (男C + 男D)
对手对:
  - 男A vs 男C（同性：DB 侧对手）→ 'M' + min(A,C) + ',M' + max(A,C)
  - 男A vs 男D（同性：DB 侧对手）→ 'M' + min(A,D) + ',M' + max(A,D)
  - 女B 在本场没有女性对手对位 → 不计
```

#### 代码改动

在 `go_exact` 的 XW/XD 段（Python + JS），match 记录之后加上：

```python
# XW
matches.append((r + 1, 'XW', (sm, sw_mx), (swb0, swb1)))
# ↑ 已有

# ↓ 新增：对手记录
#   MX侧女 vs WB侧女0
w_opp1 = 'W' + str(min(sw_mx, swb0)) + ',W' + str(max(sw_mx, swb0))
opp_counters[w_opp1] = opp_counters.get(w_opp1, 0) + 1
#   MX侧女 vs WB侧女1
w_opp2 = 'W' + str(min(sw_mx, swb1)) + ',W' + str(max(sw_mx, swb1))
opp_counters[w_opp2] = opp_counters.get(w_opp2, 0) + 1
```

```python
# XD
matches.append((r + 1, 'XD', (sm_mx, sw), (sdb0, sdb1)))
# ↑ 已有

# ↓ 新增：对手记录
#   MX侧男 vs DB侧男0
m_opp1 = 'M' + str(min(sm_mx, sdb0)) + ',M' + str(max(sm_mx, sdb0))
opp_counters[m_opp1] = opp_counters.get(m_opp1, 0) + 1
#   MX侧男 vs DB侧男1
m_opp2 = 'M' + str(min(sm_mx, sdb1)) + ',M' + str(max(sm_mx, sdb1))
opp_counters[m_opp2] = opp_counters.get(m_opp2, 0) + 1
```

### 代码改动清单

| 文件 | 位置 | 改动 |
|------|------|------|
| `tennis_scheduler.py` | `go_exact()` XW 段 | 追加 opp_counters 写入（女 vs 女 × 2） |
| `tennis_scheduler.py` | `go_exact()` XD 段 | 追加 opp_counters 写入（男 vs 男 × 2） |
| `index.html` | `go_exact()` XW/XD 段 | 同上 |

---

# 第2步：统一分组引擎

## 2.1 现状问题

当前 `go_exact` 的分组逻辑是 **按类型顺序处理**：

```
每轮：
  1. 先处理特殊场地 XW/XD（若有）
  2. 处理 roundCounters（固定配对约束）
  3. 处理 DB（从剩余男子中取 need_db 人）
  4. 处理 WB（从剩余女子中取 need_wb 人）
  5. 处理 MX（用剩下的男女配对）
```

**问题：**
- DB/WB/MX 各自独立处理，每个类型不知道其他类型的存在
- 选手选择顺序不稳定（先到先得）
- MX 拿到的总是 DB/WB 挑剩下的选手，质量无法保证
- 全局视角缺失

## 2.2 统一分组引擎设计

### 核心思路

每轮开始时，把**所有选手**看作一个整体，按**场地类型**统一规划：

```
[每轮入口]
       │
       ▼
┌─────────────────────────────────────┐
│         统一分组引擎                   │
│                                      │
│  输入：本轮分布 (a,b,c,special)      │
│       可用选手池 (avail_m, avail_w)  │
│       全局状态 (usedPairs, oppCount) │
│       约束列表 (roundCounters)       │
│                                      │
│  步骤：                              │
│  1. 预占：特殊场地选手（若有）       │
│  2. 预占：固定配对约束选手            │
│  3. 构建分组方案：                    │
│     对所有选手做类型分配              │
│     (谁打DB、谁打WB、谁打MX)          │
│  4. 执行分组：                        │
│     DB组 → enumerate_pairings        │
│     WB组 → enumerate_pairings        │
│     MX组 → hungarian                 │
│     XW/XD → _pick_xw / _pick_xd     │
│  5. 更新全局状态                      │
└─────────────────────────────────────┘
```

### 2.3 核心：选手类型分配（Group Allocator）

**问题建模**：

```
输入：
  M_avail = 可用男选手列表（不含特殊场地和固定约束已占用的）
  W_avail = 可用女选手列表
  need_db = 4a（本轮需要多少男人次打DB）
  need_wb = 4b（本轮需要多少女人次打WB）
  need_mx = 2c（本轮需要多少男人次+女人次打MX）
  
输出：
  group_db = [男选手] 打DB的
  group_wb = [女选手] 打WB的
  group_mx_men = [男选手] 打MX的
  group_mx_women = [女选手] 打MX的
  
约束：
  |group_db| = need_db
  |group_wb| = need_wb
  |group_mx_men| = |group_mx_women| = need_mx
  group_db + group_mx_men ⊆ M_avail（互斥）
  group_wb + group_mx_women ⊆ W_avail（互斥）
```

### 分配策略（贪心评分）

不再按固定顺序挑人，而是对**每个选手**计算"打DB的适合度"和"打MX的适合度"，按全局最优分配。

#### 评分函数

```python
def assign_type_score(player, gender, target_type, levels, used_pairs, opp_counters, existing_group):
    """
    计算将 player 分配到 target_type 组的适合度（越低越好）
    """
    score = 0.0
    
    if target_type == 'DB':
        # DB 适合度：水平接近的同伴更易配对
        #   - 池中还有谁（已有 group_db 成员）
        for peer in existing_group:
            pair_key = 'M' + str(min(player, peer)) + ',M' + str(max(player, peer))
            if pair_key in used_pairs:
                score += INF / 4  # 尽量选未搭档过的
            score += abs(levels[player] - levels[peer])  # 水平差
        #   - 对手成本：和可能对位的男选手的对手历史
        #     粗略估算：所有可能对手的平均对手次数
        #     (精确对位由 enumerate_pairings 决定，这里只是分配)
        pass
    
    elif target_type == 'MX':
        # MX 适合度：
        #   - 跨性别对手关系（此男和女选手们的历史）
        #   - 水平差（和可能的异性别搭档）
        pass
    
    elif target_type == 'WB':
        # 类似 DB 但针对女性
        pass
    
    return score
```

**简化方案**（先实现这个，后续优化）：

按**轮次分布计算出的需求数**做贪心分配，优先级队列决定谁去哪个组：

```python
def allocate_players(M_avail, W_avail, need_db, need_wb, need_mx, 
                     levels, used_pairs, opp_counters):
    """
    贪心分配选手到 DB/WB/MX 组
    返回: (group_db, group_wb, group_mx_men, group_mx_women)
    """
    m_men = list(M_avail)
    m_women = list(W_avail)
    
    # 策略：先按"灵活性"排序——水平中等的优先分配（避免极端水平卡在不适配的类型）
    # 简化版：按水平排序，DB/WB 先挑水平接近的，MX 挑剩下的
    
    # 方案 A（优先实现）：保持现有 DB→WB→MX 的固定顺序，
    # 但增加"选手评分"，让 DB 和 MX 能根据历史做智能选择
    
    # ===== 步骤1: DB 分配（男子选 need_db 人） =====
    # 对每个男选手计算"DB损失分"
    db_scores = {}
    for p in m_men:
        s = 0.0
        # 和可能搭档的组合评分
        for p2 in m_men:
            if p2 == p: continue
            pair_key = 'M' + str(min(p, p2)) + ',M' + str(max(p, p2))
            if pair_key in used_pairs:
                s += 50  # 未搭档过优先
        db_scores[p] = s
    
    # 按 DB 适合度排序，取 need_db 个
    db_candidates = sorted(m_men, key=lambda p: db_scores[p])
    group_db = db_candidates[:need_db]
    remaining_m = [p for p in m_men if p not in group_db]  # → 打 MX
    
    # ===== 步骤2: WB 分配（女子选 need_wb 人） =====
    wb_scores = {}
    for p in m_women:
        s = 0.0
        for p2 in m_women:
            if p2 == p: continue
            pair_key = 'W' + str(min(p, p2)) + ',W' + str(max(p, p2))
            if pair_key in used_pairs:
                s += 50
        wb_scores[p] = s
    
    wb_candidates = sorted(m_women, key=lambda p: wb_scores[p])
    group_wb = wb_candidates[:need_wb]
    remaining_w = [p for p in m_women if p not in group_wb]  # → 打 MX
    
    # ===== 步骤3: MX = 剩余选手 =====
    group_mx_men = remaining_m[:need_mx]
    group_mx_women = remaining_w[:need_mx]
    
    return group_db, group_wb, group_mx_men, group_mx_women
```

### 2.4 约束作为前置条件

在当前顺序处理的基础上，约束（roundCounters 中的固定配对）在其他任何分组之前**预先占位**：

```
统一分组引擎入口
  │
  ├─ [1] 特殊场地占用（若有 XW/XD）
  │      从 avail_m / avail_w 中移除占用者
  │
  ├─ [2] 固定配对约束占用（roundCounters）
  │      逐个检查 roundCounters 中 remaining > 0 的约束
  │      如果本轮有容量（need_db/need_wb/need_mx 够）
  │      则直接放置，从 avail 中移除占用者，更新 need 计数
  │
  ├─ [3] 选手分组（allocate_players）
  │      用剩余的 avail_m / avail_w 做贪心分配
  │
  ├─ [4] 组内配对
  │      DB组 → enumerate_pairings
  │      WB组 → enumerate_pairings
  │      MX组 → hungarian + build_cost_matrix
  │
  └─ [5] 更新全局计数器 & 对手记录
```

### 2.5 特殊场地补充逻辑

特殊场地（XW/XD）的选手选择仍然使用 `_pick_xw` / `_pick_xd`，但**增加对手感知**（第1步已做）。

在分组引擎中，特殊场地放在第1步（最高优先级），理由：
- 特殊场地选手组成特殊（1M+3W 或 3M+1W），不参与标准的 DB/WB/MX 分组
- 先选定特殊场地可以降低后续分组复杂度
- 特殊的对手记录仍需写入 opp_counters（第1步）

---

## 2.6 统一分组引擎完整伪代码

```python
def fill_round_exact(r, dist_entry, M, W, round_counters, opp_counters,
                     used_pairs, used_mx_pairs, used_smx, used_swb, used_sdb,
                     male_levels, female_levels):
    """
    统一分组引擎 — 一轮填充
    返回: [(round, type, t1, t2), ...] 或 None
    """
    a, b, c, special = dist_entry
    need_db = 4 * a
    need_wb = 4 * b
    need_mx = 2 * c
    
    # 可用选手（基于已有 match 计数计算）
    mc = compute_male_counts(existing_matches, r)
    fc = compute_female_counts(existing_matches, r)
    avail_m = [mi for mi in range(M) if mc[mi] == r]
    avail_w = [wi for wi in range(W) if fc[wi] == r]
    
    round_matches = []
    spec_m = []
    spec_w = []
    
    # ===== [步骤1] 特殊场地 =====
    if special == 'XW':
        p = _pick_xw(r, M, W, used_smx, used_swb, male_levels, female_levels)
        if not p: return None
        sm, sw_mx, swb0, swb1 = p
        spec_m.append(sm); spec_w.extend([sw_mx, swb0, swb1])
        used_smx.add(str(sm) + ',' + str(sw_mx))
        used_swb.add(str(min(swb0, swb1)) + ',' + str(max(swb0, swb1)))
        round_matches.append((r + 1, 'XW', (sm, sw_mx), (swb0, swb1)))
        # 对手记录（第1步新增）
        for w_opp in [swb0, swb1]:
            wk = 'W' + str(min(sw_mx, w_opp)) + ',W' + str(max(sw_mx, w_opp))
            opp_counters[wk] = opp_counters.get(wk, 0) + 1
    elif special == 'XD':
        p = _pick_xd(r, M, W, used_smx, used_sdb, male_levels, female_levels)
        if not p: return None
        sm_mx, sw, sdb0, sdb1 = p
        spec_m.extend([sm_mx, sdb0, sdb1]); spec_w.append(sw)
        used_smx.add(str(sm_mx) + ',' + str(sw))
        used_sdb.add(str(min(sdb0, sdb1)) + ',' + str(max(sdb0, sdb1)))
        round_matches.append((r + 1, 'XD', (sm_mx, sw), (sdb0, sdb1)))
        # 对手记录（第1步新增）
        for m_opp in [sdb0, sdb1]:
            mk = 'M' + str(min(sm_mx, m_opp)) + ',M' + str(max(sm_mx, m_opp))
            opp_counters[mk] = opp_counters.get(mk, 0) + 1
    
    # 从 avail 中移除特殊场地占用者
    avail_m = [p for p in avail_m if p not in spec_m]
    avail_w = [p for p in avail_w if p not in spec_w]
    
    # ===== [步骤2] 固定约束占位 =====
    rc_used = []
    for rck in list(round_counters.keys()):
        rc = round_counters[rck]
        if not rc or rc['remaining'] <= 0: continue
        fc = rc['constraint']
        genders = fc['genders']
        is_db = genders == 'MMMM'
        is_wb = genders == 'WWWW'
        is_mx = genders in ('MWMW', 'WMWM', 'MWWM', 'WMMW')
        
        # 检查本轮容量
        need = 4 if is_db or is_wb else 2
        has_cap = (is_db and need_db >= need) or \
                  (is_wb and need_wb >= need) or \
                  (is_mx and need_mx >= need)
        if not has_cap: continue
        
        # 放置约束
        if is_db:
            need_db -= 4
            rc_used.append((rck, (r+1, 'DB', (fc['a'], fc['b']), (fc['c'], fc['d']))))
        elif is_wb:
            need_wb -= 4
            rc_used.append((rck, (r+1, 'WB', (fc['a'], fc['b']), (fc['c'], fc['d']))))
        elif is_mx:
            need_mx -= 2
            m1 = fc['a'] if genders[0] == 'M' else fc['b']
            w1 = fc['b'] if genders[0] == 'M' else fc['a']
            m2 = fc['c'] if genders[2] == 'M' else fc['d']
            w2 = fc['d'] if genders[2] == 'M' else fc['c']
            rc_used.append((rck, (r+1, 'MX', (m1, w1), (m2, w2))))
    
    # 提交约束占位（确保资源释放如果失败）
    for rck, match in rc_used:
        round_matches.append(match)
        round_counters[rck]['remaining'] -= 1
        # 从 avail 中移除占用选手
        t1, t2 = match[2], match[3]
        for p in t1 + t2:
            gender = 'M' if (match[1] in ('DB', 'XD') or 
                            (match[1] == 'MX' and p in [t1[0], t2[0]])) else 'W'
            # 简化处理：直接用索引判断性别
            if match[1] in ('DB',):
                avail_m = [x for x in avail_m if x not in t1 + t2]
            elif match[1] in ('WB',):
                avail_w = [x for x in avail_w if x not in t1 + t2]
            elif match[1] in ('MX', 'MB'):
                avail_m = [x for x in avail_m if x not in (t1[0], t2[0])]
                avail_w = [x for x in avail_w if x not in (t1[1], t2[1])]
    
    # ===== [步骤3] 选手分组（统一分配） =====
    group_db, group_wb, group_mx_men, group_mx_women = \
        allocate_players(avail_m, avail_w, need_db, need_wb, need_mx,
                        male_levels, female_levels, used_pairs, opp_counters)
    
    # ===== [步骤4] 组内配对 =====
    # DB
    for di in range(0, len(group_db), 4):
        four = group_db[di:di+4]
        if len(four) < 4: continue
        ep = enumerate_pairings(four, male_levels, used_pairs, opp_counters, 'M')
        if not ep: return None
        p1, p2 = ep['pairs'][0], ep['pairs'][1]
        round_matches.append((r + 1, 'DB', p1, p2))
        _mark_pair(p1[0], p1[1], 'M')
        _mark_pair(p2[0], p2[1], 'M')
        _add_opp(p1[0], p2[0], 'M')
        _add_opp(p1[0], p2[1], 'M')
        _add_opp(p1[1], p2[0], 'M')
        _add_opp(p1[1], p2[1], 'M')
    
    # WB
    for wi_idx in range(0, len(group_wb), 4):
        four = group_wb[wi_idx:wi_idx+4]
        if len(four) < 4: continue
        ep = enumerate_pairings(four, female_levels, used_pairs, opp_counters, 'W')
        if not ep: return None
        p1, p2 = ep['pairs'][0], ep['pairs'][1]
        round_matches.append((r + 1, 'WB', p1, p2))
        _mark_pair(p1[0], p1[1], 'W')
        _mark_pair(p2[0], p2[1], 'W')
        _add_opp(p1[0], p2[0], 'W')
        _add_opp(p1[0], p2[1], 'W')
        _add_opp(p1[1], p2[0], 'W')
        _add_opp(p1[1], p2[1], 'W')
    
    # MX
    if len(group_mx_men) > 0 and len(group_mx_men) == len(group_mx_women):
        matrix = build_cost_matrix(group_mx_men, group_mx_women, used_mx_pairs,
                                  male_levels, female_levels, opp_counters)
        if not matrix: return None
        # 匈牙利 + 组装（同现有逻辑，增加对手验证）
        assign = hungarian(matrix)
        for ci in range(len(group_mx_men) // 2):
            m1 = group_mx_men[2*ci]
            w1 = group_mx_women[assign[2*ci]]
            m2 = group_mx_men[2*ci+1]
            w2 = group_mx_women[assign[2*ci+1]]
            
            # 对手硬检查（第1步新增）
            m_key = 'M' + str(min(m1,m2)) + ',M' + str(max(m1,m2))
            w_key = 'W' + str(min(w1,w2)) + ',W' + str(max(w1,w2))
            if opp_counters.get(m_key, 0) >= 3: return None
            if opp_counters.get(w_key, 0) >= 3: return None
            
            round_matches.append((r + 1, 'MX', (m1, w1), (m2, w2)))
            used_mx_pairs.add(str(m1) + ',M' + str(w1))
            used_mx_pairs.add(str(m2) + ',M' + str(w2))
            opp_counters[m_key] = opp_counters.get(m_key, 0) + 1
            opp_counters[w_key] = opp_counters.get(w_key, 0) + 1
    
    return round_matches
```

---

## 代码结构变动总结

### 修改的函数

| 函数 | 所属 | 改动说明 |
|------|------|---------|
| `build_cost_matrix()` | Python + JS | 增加 `opp_counters` 参数，对手成本计算 |
| `go_exact()` | Python + JS | 重构为调用 `fill_round_exact`，拆分为统一的逐轮处理 |

### 新增的函数

| 函数 | 所属 | 说明 |
|------|------|------|
| `allocate_players()` | Python + JS | 统一分组引擎 — 选手类型分配 |
| `fill_round_exact()` | Python + JS | 统一分组引擎 — 一轮填充（整合特殊场地+约束+分配+配对） |

### 不变/轻微改动的函数

| 函数 | 说明 |
|------|------|
| `enumerate_pairings()` | 不变，已含 opp_counters 检查 |
| `hungarian()` | 不变 |
| `_pick_xw()` / `_pick_xd()` | 不变 |
| `construct_dist()` | 不变 |
| `verifyConstraints()` | 不变 |

---

## 实现顺序建议

```
第1步（先做，改动小）：
  1.1 build_cost_matrix 加 opp_counters → 32 行代码
  1.2 XW/XD 加对手记录 → 12 行代码
  → 改动约 44 行，可独立验证

第2步（后做，结构调整）：
  2.1 实现 allocate_players() → 40 行
  2.2 实现 fill_round_exact() → 集成现有逻辑 → 60 行
  2.3 go_exact() 改为调用 fill_round_exact() → 20 行
  → 改动约 120 行，替换现有 go_exact 内部逻辑
```
