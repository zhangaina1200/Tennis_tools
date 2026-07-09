# Plan A — 算法重构技术方案

## 一、现状与问题

### 当前架构（纯随机搜索）

```
generate()
  ├─ getAllDists() → filterByMinRequirements() → sortDistsByMode()
  ├─ 主循环（按排序逐个分布尝试）
  │    对每个分布，调用 _go() 最多 tries 次
  │      └─ 逐轮填充（flexPair/flexMix 随机配对）
  │    生成后 verifyConstraints() 验证
  └─ Fallback（兜底分布填充）
```

| 痛点 | 表现 | 根因 |
|------|------|------|
| **慢** | 8M8W+约束 ~60秒+ | `flexPair` 随机搜索 O(N!), N=8时~40320种排列 |
| **不可靠** | 同一配置有时成功有时失败 | 纯随机，无法保证在 tries 次内找到解 |
| **确定性差** | [1,1,2] 分布屡次失败 | DB 选择 + 配对双重随机，关键路径概率低 |

### 核心瓶颈：flexPair 的随机搜索

`flexPair` 对 4 个选手（DB/WB）做全排列搜索（最多 4!=24 种），`flexMix` 对 2m 男+2m 女做排列搜索（最多 (2m)! 种）。

当 `usedDB`/`maxCountDB` 累积了大量限制后，随机搜索的成功率急剧下降。

---

## 二、总体设计

### 新架构（确定性图匹配）

```
generate()
  ├─ getAllDists() → filterByMinRequirements() → sortDistsByMode()  [不变]
  │
  ├─ 全局计数器初始化（N场约束、对手次数）
  │     ├─  roundCounter: {约束ID → 剩余场次}
  │     └─  oppCounter: {pair_key → 已对阵次数}
  │
  ├─ 主循环（按排序逐个分布尝试，确定性）
  │    对每个分布，调用 go_exact() 1次（不随机重试）
  │      └─ 逐轮填充：
  │             DB:  排序选4人 → 遍历/匈牙利找最优配对
  │             WB:  排序选4人 → 遍历/匈牙利找最优配对  
  │             MX:  匈牙利求最小权完美匹配（男女搭配）
  │      └─ 成功后 verifyConstraints()
  │
  └─ Fallback（不随机，用兜底模式）
```

### 核心改动

| 模块 | 旧（随机） | 新（确定性） |
|------|-----------|------------|
| DB/WB配对 | `flexPair` 随机排列搜索 | 遍历全部N!种配对，选评分最优 |
| MX搭配 | `flexMix` 随机排列搜索 | 匈牙利算法 O(m³) 最小权完美匹配 |
| 约束管理 | `preAllocMap` 预分配轮次 | 全局 `roundCounter` 计数器 |
| 对手限制 | 无 | `oppCounter` 计数器 ≤3 |
| 重试策略 | 3000次随机重试 | 0次重试（不依赖随机） |
| N场约束 | 要求连续轮次 | 不要求连续，任意轮次凑满N场 |

---

## 三、模块详细设计

### 3.1 匈牙利算法实现

**适用场景**：MX 混合配对（二分图完美匹配）

#### 问题建模

```
输入：m 个男选手 M = {m₁, m₂, ..., mₘ}
      m 个女选手 W = {w₁, w₂, ..., wₘ}
      （注：m 为偶数，每2男+2女构成1场比赛）

输出：m 对 (mᵢ, wⱼ)，每对不重复使用选手
      且按权重成本最小化

权重矩阵 W[i][j] = cost(mᵢ, wⱼ)
```

#### 权重计算

```
cost(m_i, w_j) = 
  α₁ × |level(m_i) - level(w_j)|     ← 水平差
  + α₂ × pairRepeatPenalty(m_i, w_j)  ← 搭档重复惩罚（∞ 如果已搭过）
  + α₃ × oppPenalty(m_i, w_j)          ← 对手次数惩罚
```

其中：
- `pairRepeatPenalty` = 如果 (mᵢ, wⱼ) 已经组队过 → INF（禁止重复）
- `oppPenalty` = 对手在剩余场次中能否搭配（查询 `oppCounter`）

#### 算法流程（标准匈牙利）

```
hungarian(costMatrix):
  // 输入：m×m 成本矩阵
  // 输出：最小权完美匹配的 paired list
  
  1. 行规约：每行减去最小值
  2. 列规约：每列减去最小值
  3. 用最小线数覆盖所有0
  4. 如果线数 == m → 找到最优解
  5. 否则：调整矩阵 → 回到步骤3
  
  return matchResult = [(m_0,w_j0), (m_1,w_j1), ...]
```

**复杂度**：O(m³)，m ≤ 8（每轮最多4对混双），运行时间 < 1ms

### 3.2 DB/WB 配对优化

**场景**：4人 → 2个双打队伍

4 人配对成 2 个双打队伍只有 **3种可能性**：

```
4人 [A,B,C,D] 的配对方式：
  ① [A+B] [C+D]
  ② [A+C] [B+D]
  ③ [A+D] [B+C]
```

**不需要匈牙利算法**，直接遍历 3 种，各算评分取最优：

```
score(pairing) = 
  β₁ × sum(|level(a) - level(b)|)             ← 搭档水平差和
  + β₂ × opponentBalanceScore(match)            ← 对阵平衡
  + partnerRepeatPenalty                        ← 队友重复（INF）
```

复杂度 O(3)，< 0.01ms。

### 3.3 全局计数器

废除 `preAllocMap` 的轮次预分配，改用全局计数器。

#### 数据结构

```typescript
interface GlobalState {
  // N场约束
  roundCounters: {
    [constraintId: string]: {
      remaining: number;       // 剩余还需安排的场次
      total: number;           // 要求的场次总数
      constraint: Constraint;  // 原始约束对象
    }
  };
  
  // 对手次数
  oppCounters: {
    [pairKey: string]: number; // "min(p1,p2),max(p1,p2)" → 已对阵次数
  };
  
  // 搭档已用
  usedPairs: Set<string>;      // 所有比赛类型的搭档键
}
```

#### 处理流程

```
每轮开始：
  // 1. 检查还有哪些 N 场约束未完成
  activeConstraints = roundCounters.filter(c => c.remaining > 0)
  
  // 2. 优先安排未完成的约束
  for each constraint in activeConstraints:
    try place constraint in this round
    if success:
      roundCounters[constraintId].remaining--
  
  // 3. 剩余选手按常规填充（DB/WB/MX）
  fillRemainingPlayers()
  
  // 4. 更新 oppCounters
  for each match in this round:
    update oppCounters for opponents
  
  // 5. 更新 usedPairs
  for each team pair:
    add to usedPairs
```

### 3.4 对手 ≤3 次限制

#### 规则

同一对选手（不论比赛类型，男双女双混双合并统计）在整个赛程中最多对阵 3 次。

#### 实现

```typescript
// 每安排一场比赛后更新
function updateOppCounter(p1, p2, type) {
  const key = min(p1, p1Gender, p2, p2Gender) + ',' + max(p1, p1Gender, p2, p2Gender);
  // 注意：男女索引可能冲突（男6 vs 女6），需要区分性别
  // 方案：key = "M" + p1 + "," + "W" + p2 (格式化为 gender+index)
  oppCounters[key] = (oppCounters[key] || 0) + 1;
}

// 检查是否允许配对
function canBeOpponents(p1, p1g, p2, p2g) {
  const key = buildKey(p1, p1g, p2, p2g);
  return (oppCounters[key] || 0) < 3;
}
```

**性别索引冲突处理**：男选手和女选手可能使用相同的索引数字（如男6和女6都是数字6）。在 `oppCounters` 的 key 中必须**加上性别前缀**：

```
男6 vs 女3 → key = "M6,W3"
女6 vs 男3 → key = "W6,M3"
```

### 3.5 约束优先级（重述确认）

```
1️⃣ 指定N场（rounds>1）→ 全局计数器安排N次，不要求连续
2️⃣ 指定1场约束 → 当轮优先安排
3️⃣ 搭档严格不重复 → INF惩罚，禁止同对
4️⃣ 对阵≤3次 → oppCounter ≤ 3
5️⃣ 场次偏好 → 分布层面筛选
6️⃣ 水平均衡 → 权重计入成本函数
```

### 3.6 add-round 适配

#### 场景分类

| 场景 | 规则 | 实现 |
|------|------|------|
| **a) 首次生成后直接添加轮次** | 新轮次内部严格，不与历史比较 | 独立生成，不继承 `usedPairs`/`oppCounter` |
| **b) 删除后再添加** | 记住历史直接显示 | 保留原结果，不重新生成 |
| **c) 在b基础上再加** | 同场景a | 独立生成 |

#### 实现方案

```typescript
function addRound(existingMatches, existingUsedPairs, existingOppCount, 
                   M, W, players) {
  // 场景a/c：新轮次独立生成
  const newRound = {
    matches: [],
    usedPairs: new Set(),          // 从空开始
    oppCounts: {},                 // 从空开始
  };
  
  // 按当前模式（mixed/default/doubles）选择分布
  const newDist = computeSingleRoundDist(M, W, mode, existingMatches);
  
  // 填充新轮次（内部严格）
  fillRound(newRound, newDist, M, W, players);
  
  return newRound;
}
```

#### 单轮分布计算

```typescript
function computeSingleRoundDist(M, W, mode, existingMatches) {
  // 统计已有比赛的分布
  const dbSoFar = countByType(existingMatches, 'DB');
  const wbSoFar = countByType(existingMatches, 'WB');
  const mxSoFar = countByType(existingMatches, 'MX');
  
  // 根据模式推荐新轮次类型
  if (mode === 'mixed' && mxSoFar < 10) {
    return { a: 1, b: 1, c: 2 };  // 2MX + 1DB + 1WB
  }
  if (mode === 'doubles') {
    return { a: 2, b: 2, c: 0 };  // 2DB + 2WB
  }
  // ...其他情况
}
```

---

## 四、代码结构变动

### 4.1 新增函数

| 函数 | 说明 |
|------|------|
| `hungarian(costMatrix)` | 匈牙利算法主入口，返回最小权完美匹配 |
| `buildCostMatrix(men, women, state)` | 构建 m×m 权重矩阵 |
| `initCounters(constraints, N)` | 初始化全局计数器 |
| `placeNRoundConstraints(state)` | 在当前轮放置N场约束 |
| `updateOppCounters(state, match)` | 更新对手计数器 |
| `fillRoundExact(state, dist)` | 确定性填充一轮（替代当前随机填充） |
| `go_exact(M, W, dist, state)` | 确定性版 `_go`（不依赖随机） |

### 4.2 保留/不改的函数

| 函数 | 说明 |
|------|------|
| `getAllDists()` | 不变，继续生成分布候选 |
| `filterByMinRequirements()` | 不变 |
| `sortDistsByMode()` | 不变 |
| `getMode()` / `getLevels()` | 不变 |
| `verifyConstraints()` | 保持不变，但确定性下基本不需要验证 |
| `checkPairs()` | 保留作为安全校验 |

### 4.3 修改/废弃的函数

| 函数 | 改动 |
|------|------|
| `_go()` | 废弃，替换为 `go_exact()` |
| `flexPair()` | 废弃，替换为 `enumeratePairings()` |
| `flexMix()` | 废弃，替换为匈牙利算法 |
| `generate()` | 主流程修改：不再循环 tries 次，改为确定性单次尝试 |
| Fallback | 保留但简化，作为 `go_exact()` 失败时兜底 |

---

## 五、实现计划

### Phase 1：核心函数（建议优先实现并测试）

```
1. enumeratePairings(players, levels, usedPairs)
   → 遍历4人的3种配对，选评分最优
   → 替换 flexPair

2. hungarian(costMatrix)
   → 标准匈牙利算法实现
   → O(n³) 复杂度 ≤ 512 次操作

3. go_exact(M, W, dist, state)
   → 整合 enumeratePairings + hungarian
   → 确定性填充一轮
```

### Phase 2：约束管理

```
4. initCounters / placeNRoundConstraints
   → 全局计数器管理N场约束

5. oppCounter 实现
   → 对手≤3次限制
   → 性别前缀区分 M/W 索引
```

### Phase 3：集成与验证

```
6. generate() 改造
   → 移除 tries 循环
   → 集成 go_exact
   
7. add-round 适配
   → 新轮次独立生成逻辑
   
8. 全面测试
   → 8M8W 各种模式+约束组合
   → 奇偶人数场景
   → 指定N场精确验证
```

---

## 六、预期提升

| 指标 | 当前（随机搜索） | Plan A（图匹配） |
|------|---------------|----------------|
| 8M8W无约束 | ~1-3秒 | < 10ms |
| 8M8W+约束 | ~60秒+ | < 50ms |
| 成功率 | ~95%（3000次） | 100% |
| 确定性 | ❌ 同配置可能不同结果 | ✅ 同配置→同结果 |
| 队友重复 | 0（checkPairs） | 0（硬性禁止） |
| 对手≤3 | ❌ 未实现 | ✅ 内置实现 |
| 代码复杂度 | 2000+行 | ~800行（精简） |

---

娜姐你看看这个方案，有需要调整的地方吗？没问题的话我先开始写 Phase 1 的核心函数（配对遍历+匈牙利算法+`go_exact`）。
