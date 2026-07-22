# -*- coding: utf-8 -*-
"""
双色球第4步：筛选4个备选蓝球 + 规划5组差异化红球组合
========================================================
依赖: ssq_raw_20.csv (单一数据源) / ssq_red_coldhot.csv (冷热分类)
规则: 复用第3步硬性过滤 R1(奇偶比2-4) R2(AC值6-9) R3(三区1-4)
      + 本步新增: 禁止三连号(≥3连续) / 5组两两重复≤2个 / 每组含≥1热且≥1冷
产出: ssq_blue_candidates.csv / ssq_groups_5.csv / 双色球选号组合.html
免责: 开奖为独立随机事件，以下仅为数据存档与参考，不构成购彩建议。
"""
import csv, os, itertools, random
from collections import Counter

def _resolve_data_dir(env_name="SSQ_DATA"):
    # 兼容 Windows + Git Bash: os.getcwd()/环境变量可能返回 /x/... 形式的 POSIX 路径,
    # Windows 原生 Python 会误判为 C:/x/... 而找不到目录, 这里归一化为 X:/...
    p = os.environ.get(env_name, os.getcwd())
    if os.name == "nt" and len(p) >= 3 and p[0] == "/" and p[1].isalpha() and p[2] == "/":
        p = p[1].upper() + ":" + p[2:]
    return p

OUT_DIR = _resolve_data_dir("SSQ_DATA")
random.seed(20260719)

# ---------------------------------------------------------------------------
# 1. 读取数据源
# ---------------------------------------------------------------------------
def load_raw():
    rows = []
    with open(os.path.join(OUT_DIR, "ssq_raw_20.csv"), encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            reds = [int(row[f"红{i}"]) for i in range(1, 7)]
            rows.append((row["期号"], row["开奖日期"], reds, int(row["蓝"])))
    return rows

def load_classes():
    hot, warm, cold = set(), set(), set()
    with open(os.path.join(OUT_DIR, "ssq_red_coldhot.csv"), encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            n, c = int(row["号码"]), row["分类"]
            (hot if c == "热" else warm if c == "温" else cold).add(n)
    return hot, warm, cold

# ---------------------------------------------------------------------------
# 2. 蓝球统计与4个备选筛选
# ---------------------------------------------------------------------------
def blue_stats(rows):
    cnt = Counter(b for *_, b in [(r[0], r[1], r[2], r[3]) for r in rows])
    # rows[0] 为最新一期(遗漏索引0)；last_idx[b]=最近一次出现的索引
    last_idx = {}
    for idx, (_, _, _, b) in enumerate(rows):
        if b not in last_idx:        # rows 为最新→最早，首次遇到=最小索引=最近一期
            last_idx[b] = idx
    n = len(rows)
    stats = {}
    for b in range(1, 17):
        freq = cnt.get(b, 0)
        omission = last_idx[b] if b in last_idx else n
        stats[b] = (freq, omission)
    return stats

def select_blues(stats):
    mean_omit = sum(v[1] for v in stats.values()) / 16.0
    active = sorted([b for b in stats if stats[b][1] < mean_omit],
                    key=lambda b: (stats[b][1], -stats[b][0]))          # 遗漏短优先
    due = sorted([b for b in stats if stats[b][1] >= mean_omit],
                 key=lambda b: (-stats[b][1], b))                        # 遗漏长优先
    candidates = (active[:2] + due[:2])
    return candidates, mean_omit, active, due

# ---------------------------------------------------------------------------
# 3. 红球组合规则与枚举
# ---------------------------------------------------------------------------
def odd_count(nums):   return sum(1 for n in nums if n % 2 == 1)

def zone_counts(nums):
    z = [0, 0, 0]
    for n in nums:
        z[0 if n <= 11 else 1 if n <= 22 else 2] += 1
    return tuple(z)

def ac_value(nums):
    diffs = set()
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            diffs.add(nums[j] - nums[i])
    return len(diffs) - 5

def has_three_run(nums):
    run = 1
    for i in range(1, len(nums)):
        if nums[i] == nums[i - 1] + 1:
            run += 1
            if run >= 3:
                return True
        else:
            run = 1
    return False

def is_valid(nums, hot, warm, cold):
    if not (2 <= odd_count(nums) <= 4):          return False   # R1
    if not (6 <= ac_value(nums) <= 9):            return False   # R2
    if any(c < 1 or c > 4 for c in zone_counts(nums)): return False  # R3
    if has_three_run(nums):                       return False   # 禁止三连号
    return True

def build_pool(hot, warm, cold):
    pool = []
    for combo in itertools.combinations(range(1, 34), 6):
        nums = list(combo)
        if not is_valid(nums, hot, warm, cold):
            continue
        h = sum(1 for n in nums if n in hot)
        w = sum(1 for n in nums if n in warm)
        c = sum(1 for n in nums if n in cold)
        if h < 1 or c < 1:                        # 每组含≥1热且≥1冷(平衡参考)
            continue
        bal = -(abs(h - 2) + abs(w - 2) + abs(c - 2))   # 越接近2/2/2越好
        pool.append((tuple(nums), frozenset(nums), h, w, c, bal))
    return pool

# ---------------------------------------------------------------------------
# 4. 差异化选组(贪心: 两两重复≤2, 整体覆盖最广)
# ---------------------------------------------------------------------------
def select_groups(pool, k=5, max_overlap=2):
    pool_sorted = sorted(pool, key=lambda c: (c[5], c[0]), reverse=True)
    chosen = [pool_sorted[0]]
    union = set(chosen[0][1])
    while len(chosen) < k:
        best, bestkey = None, None
        for c in pool:
            nums = c[1]
            if any(len(nums & ch[1]) > max_overlap for ch in chosen):
                continue
            marginal = len(nums - union)
            key = (marginal, c[5], c[0])          # 新增号码多 > 均衡 > 号码小
            if bestkey is None or key > bestkey:
                bestkey, best = key, c
        if best is None:
            max_overlap += 1
            continue
        chosen.append(best)
        union |= best[1]
    return chosen, max_overlap

# ---------------------------------------------------------------------------
# 5. 输出
# ---------------------------------------------------------------------------
def write_blue_csv(stats, candidates):
    path = os.path.join(OUT_DIR, "ssq_blue_candidates.csv")
    cand_set = set(candidates)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["蓝球", "出现次数", "当前遗漏(期)", "类型", "是否入选备选"])
        for b in range(1, 17):
            freq, om = stats[b]
            typ = "近期活跃" if b in candidates and om < (sum(v[1] for v in stats.values())/16) else ("冷门待出" if b in candidates else ("近期活跃" if om < sum(v[1] for v in stats.values())/16 else "冷门待出"))
            w.writerow([f"{b:02d}", freq, om, typ, "✔" if b in cand_set else ""])
    return path

def write_groups_csv(groups, blue_of):
    path = os.path.join(OUT_DIR, "ssq_groups_5.csv")
    # 两两最大重复
    def max_overlap_with(i):
        return max(len(set(groups[i][0]) & set(groups[j][0])) for j in range(len(groups)) if j != i)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["组号", "红球", "蓝球", "奇偶比", "AC值", "三区分布(一/二/三区)",
                    "热号数", "温号数", "冷号数", "与其他组最大重复数", "含三连号", "二连号数"])
        for i, (nums, _, h, w_, c, _) in enumerate(groups):
            odd = odd_count(nums)
            z = zone_counts(nums)
            two = sum(1 for j in range(1, len(nums)) if nums[j] == nums[j-1] + 1)
            w.writerow([
                f"第{i+1}组", " ".join(f"{n:02d}" for n in nums), f"{blue_of[i]:02d}",
                f"{odd}:{6-odd}", ac_value(nums), f"{z[0]}/{z[1]}/{z[2]}",
                h, w_, c, max_overlap_with(i), "否", two
            ])
    return path

def write_html(stats, candidates, groups, blue_of, max_overlap_used):
    path = os.path.join(OUT_DIR, "双色球选号组合.html")
    mean_omit = sum(v[1] for v in stats.values()) / 16
    # 蓝球表
    blue_rows = []
    for b in range(1, 17):
        freq, om = stats[b]
        typ = "近期活跃" if om < mean_omit else "冷门待出"
        sel = "✔ 备选" if b in set(candidates) else ""
        cls = "b-sel" if b in set(candidates) else ""
        blue_rows.append(f'<tr class="{cls}"><td class="num">{b:02d}</td><td class="num">{freq}</td>'
                         f'<td class="num">{om}</td><td>{typ}</td><td>{"✔" if sel else ""}</td></tr>')
    blue_html = "\n".join(blue_rows)
    # 组合表
    group_rows = []
    for i, (nums, _, h, w_, c, _) in enumerate(groups):
        odd = odd_count(nums)
        z = zone_counts(nums)
        two = sum(1 for j in range(1, len(nums)) if nums[j] == nums[j-1] + 1)
        cells = "".join(f'<td class="r">{n:02d}</td>' for n in nums)
        group_rows.append(
            f'<tr><td class="num">第{i+1}组</td>{cells}'
            f'<td class="b">{blue_of[i]:02d}</td>'
            f'<td class="num">{odd}:{6-odd}</td><td class="num">{ac_value(nums)}</td>'
            f'<td class="num">{z[0]}/{z[1]}/{z[2]}</td>'
            f'<td class="num">{h}/{w_}/{c}</td><td>否</td><td class="num">{two}</td></tr>'
        )
    group_html = "\n".join(group_rows)
    # 重复矩阵
    n = len(groups)
    mat = []
    for i in range(n):
        row = []
        for j in range(n):
            ov = len(set(groups[i][0]) & set(groups[j][0])) if i != j else 6
            color = "#fce8e8" if (i != j and ov > 2) else ("#e6f4ea" if i == j else "#fff")
            row.append(f'<td style="background:{color}">{ov}</td>')
        mat.append(f'<tr><td class="num">第{i+1}组</td>' + "".join(row) + "</tr>")
    mat_html = "\n".join(mat)
    headers = "".join(f'<th>第{j+1}组</th>' for j in range(n))
    cand_str = "、".join(f"{b:02d}" for b in candidates)

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>双色球选号组合(4蓝+5红)</title>
<style>
*{{font-family:-apple-system,"Microsoft YaHei",sans-serif;box-sizing:border-box}}
body{{margin:0;padding:24px;background:#f5f7fa;color:#1f2d3d}}
h1{{font-size:22px;margin:0 0 4px}} .sub{{color:#6b7785;font-size:13px;margin-bottom:20px}}
.card{{background:#fff;border-radius:10px;padding:18px 20px;margin-bottom:18px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.card h2{{font-size:16px;margin:0 0 12px;border-left:4px solid #d7282f;padding-left:10px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border:1px solid #e4e8ee;padding:6px 8px;text-align:center}}
th{{background:#f0f3f7;font-weight:600}} td.num{{font-variant-numeric:tabular-nums}}
td.r{{color:#d7282f;font-weight:600}} td.b{{color:#1565c0;font-weight:600}}
tr.b-sel{{background:#fff8e1}} .badge{{display:inline-block;padding:3px 10px;border-radius:12px;background:#e6f4ea;color:#137333;font-weight:600;font-size:13px}}
.note{{font-size:12px;color:#8a94a6;margin-top:14px;line-height:1.7}}
.kpis{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:6px}} .kpi{{background:#f0f3f7;border-radius:8px;padding:10px 14px;flex:1;min-width:120px}}
.kpi b{{font-size:20px;color:#d7282f;display:block}} .kpi span{{font-size:12px;color:#6b7785}}
</style></head><body>
<h1>双色球第4步 · 4个备选蓝球 + 5组差异化红球</h1>
<div class="sub">数据源：中彩网(zhcw.com) · 窗口：第2026062期~第2026081期(20期) · 生成日期：2026-07-19</div>

<div class="card"><h2>一、4个备选蓝球（筛选规则透明）</h2>
<div class="kpis">
<div class="kpi"><b>{cand_str}</b><span>入选备选蓝球</span></div>
<div class="kpi"><b>2+2</b><span>近期活跃2个 / 冷门待出2个</span></div>
<div class="kpi"><b>{mean_omit:.1f}</b><span>蓝球平均遗漏(期)</span></div>
</div>
<p class="note">规则：遗漏 &lt; 均值({mean_omit:.1f}) 归入"近期活跃"，取遗漏最短的2个；遗漏 ≥ 均值归入"冷门待出"，取遗漏最长的2个。两类互补，兼顾活跃度与待出概率。</p>
<table><thead><tr><th>蓝球</th><th>出现次数</th><th>当前遗漏</th><th>类型</th><th>入选</th></tr></thead><tbody>{blue_html}</tbody></table>
</div>

<div class="card"><h2>二、5组差异化红球组合（每组附1个备选蓝球）</h2>
<table><thead><tr><th>组号</th><th>红1</th><th>红2</th><th>红3</th><th>红4</th><th>红5</th><th>红6</th><th>蓝</th><th>奇偶比</th><th>AC</th><th>三区</th><th>热/温/冷</th><th>三连号</th><th>二连号</th></tr></thead><tbody>{group_html}</tbody></table>
<p class="note">每组均满足：R1 奇偶比2-4 · R2 AC值6-9 · R3 三区每区1-4 · 无三连号(≥3连续) · 含≥1热且≥1冷。蓝号按备选列表轮流分配，第5组复用第1个备选蓝球。</p>
</div>

<div class="card"><h2>三、差异化校验（两两红球重复数矩阵）</h2>
<table><thead><tr><th>组\组</th>{headers}</tr></thead><tbody>{mat_html}</tbody></table>
<p class="note">对角线=本组6码；非对角线=两组共同红球数。本规划约束：任意两组重复 ≤ {max_overlap_used} 个（绿色安全，红色越界）。</p>
</div>

<p class="note">⚠️ 双色球每期开奖为独立随机事件，历史号码与冷热/奇偶/AC等指标均不预示未来。以上全部为数据存档与统计分析参考，<b>不构成任何购彩建议</b>。</p>
</body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path

def main():
    rows = load_raw()
    hot, warm, cold = load_classes()
    stats = blue_stats(rows)
    candidates, mean_omit, active, due = select_blues(stats)
    pool = build_pool(hot, warm, cold)
    groups, max_overlap_used = select_groups(pool, k=5, max_overlap=2)

    blue_of = [candidates[i % len(candidates)] for i in range(len(groups))]

    bp = write_blue_csv(stats, candidates)
    gp = write_groups_csv(groups, blue_of)
    hp = write_html(stats, candidates, groups, blue_of, max_overlap_used)

    print("== 第4步 选号组合生成完成 ==")
    print(f"合法红球池规模: {len(pool):,}")
    print(f"4个备选蓝球: " + "、".join(f"{b:02d}" for b in candidates))
    print(f"  - 近期活跃: " + "、".join(f"{b:02d}" for b in active[:2]))
    print(f"  - 冷门待出: " + "、".join(f"{b:02d}" for b in due[:2]))
    print(f"两两最大重复约束: ≤{max_overlap_used}")
    all_reds = set()
    for g in groups:
        all_reds |= set(g[0])
    print(f"5组合计使用不同红球数: {len(all_reds)} / 33")
    for i, (nums, _, h, w_, c, _) in enumerate(groups):
        print(f"  第{i+1}组: " + " ".join(f"{n:02d}" for n in nums)
              + f" | 蓝{blue_of[i]:02d} | 奇偶{odd_count(nums)}:{6-odd_count(nums)} AC{ac_value(nums)} "
              + f"三区{zone_counts(nums)} 热{h}温{w_}冷{c}")

if __name__ == "__main__":
    main()
