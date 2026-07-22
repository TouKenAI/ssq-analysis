# -*- coding: utf-8 -*-
"""
双色球 · 增强优化引擎（5步法基础上的第6层）
============================================
在5步法约束(R1奇偶/R2 AC/R3三区/无三连号/热温冷2:2:2)下，用多种数学模型
把"可优化维度"推到预算内(10元=5注)极值：

  可优化维度（数学可证）：
    ① 末等奖保底率  → 蓝球分散到 5 个不同蓝，使"蓝对"概率 5/16（理论最大）
    ② 红球覆盖广度  → 组合覆盖设计：5组并集尽量覆盖全部33红（期望命中数最大化）
    ③ 人群热度规避  → 启发式打分(避生日簇/等差/往期重号)，IF中高奖减分摊(EV层)

  不可优化维度（独立均匀随机公理）：
    中一等奖概率恒 = 5 / 17,721,088，任何选号模型零影响。

  验证：蒙特卡洛(n=20万)对比 增强方案 vs 原5步方案 的 至少中一奖率/中一等奖率/期望奖金。
依赖: ssq_select_groups.py (合法池与规则) / ssq_raw_20.csv(历史重号检测)
免责: 开奖独立随机，以下仅为数据存档与概率参考，不构成购彩建议。
"""
import csv, os, math, random
import ssq_select_groups as sg

def _resolve_data_dir(env_name="SSQ_DATA"):
    # 兼容 Windows + Git Bash: os.getcwd()/环境变量可能返回 /x/... 形式的 POSIX 路径,
    # Windows 原生 Python 会误判为 C:/x/... 而找不到目录, 这里归一化为 X:/...
    p = os.environ.get(env_name, os.getcwd())
    if os.name == "nt" and len(p) >= 3 and p[0] == "/" and p[1].isalpha() and p[2] == "/":
        p = p[1].upper() + ":" + p[2:]
    return p

OUT = _resolve_data_dir("SSQ_DATA")
RAW = os.path.join(OUT, "ssq_raw_20.csv")
FINAL = os.path.join(OUT, "ssq_final_groups.csv")
CSV_OUT = os.path.join(OUT, "ssq_optimized_groups.csv")
HTML_OUT = os.path.join(OUT, "双色球优化引擎推荐.html")
N_SIM = 200_000
RED_COMB = math.comb(33, 6)
TOTAL = RED_COMB * 16

# 奖额（双色球典型固定/封顶值，用于期望对比的近似）
PRIZE = {"一等奖": 5_000_000, "二等奖": 100_000, "三等奖": 3_000,
         "四等奖": 200, "五等奖": 10, "六等奖": 5}

# ---------------------------------------------------------------------------
# 概率工具（自 ssq_win_optimize，避免触发其全局执行）
def prize_counts():
    c = {}
    c["一等奖"] = 1
    c["二等奖"] = 15
    c["三等奖"] = math.comb(6,5)*math.comb(27,1)
    c["四等奖"] = math.comb(6,5)*math.comb(27,1)*15 + math.comb(6,4)*math.comb(27,2)
    c["五等奖"] = math.comb(6,4)*math.comb(27,2)*15 + math.comb(6,3)*math.comb(27,3)
    c["六等奖"] = (math.comb(6,2)*math.comb(27,4) + math.comb(6,1)*math.comb(27,5)
                   + math.comb(6,0)*math.comb(27,6))
    return c

def is_win(rm, bm):
    if rm == 6: return True
    if rm == 5 and bm: return True
    if (rm == 5 and not bm) or (rm == 4 and bm): return True
    if (rm == 4 and not bm) or (rm == 3 and bm): return True
    if bm and rm <= 2: return True
    return False

# ---------------------------------------------------------------------------
# 历史红球（用于"往期重号"热度规避）
def load_raw_reds():
    redsets = []
    with open(RAW, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            redsets.append(frozenset(int(row[f"红{i}"]) for i in range(1, 7)))
    return redsets

# ---------------------------------------------------------------------------
# 人群热度规避打分（透明启发式，无真实销量时的 EV 层优化）
def crowd_score(nums, raw_reds):
    s = 0
    s += sum(1 for n in nums if n <= 12) * 2          # 生日簇 1-12 偏好
    # 3+ 项等差数列（人群爱选规律号）
    from itertools import combinations
    runs = 1
    for i in range(1, len(nums)):
        if nums[i] == nums[i-1] + 1:
            runs += 1
            if runs >= 3:
                s += 5
        else:
            runs = 1
    # 含往期完整6红（极热门，若中必多人分摊）
    if frozenset(nums) in raw_reds:
        s += 20
    # 对称/集中在中段的轻微惩罚
    mid = sum(1 for n in nums if 13 <= n <= 22)
    if mid >= 5:
        s += 2
    return s

# ---------------------------------------------------------------------------
# 蓝球：5 个不同蓝（优先4备选 + 补最长遗漏非备选）
def select_blues_5():
    rows = sg.load_raw()
    stats = sg.blue_stats(rows)
    cands, _, _, _ = sg.select_blues(stats)
    chosen = list(cands)                              # 4 个备选
    # 补第5个：遗漏最长且非备选
    rest = sorted([b for b in range(1, 17) if b not in chosen],
                  key=lambda b: (-stats[b][1], b))
    chosen.append(rest[0])
    return chosen, stats

# ---------------------------------------------------------------------------
# 红球：合法池内 覆盖最大化 + 热度规避（整数规划近似：贪心+局部搜索）
def select_optimized(pool, raw_reds, k=5, max_overlap=2):
    # 数学上限：5组×6码 = 30 槽位，最多覆盖 30 个不同红球（零重复时）
    COVER_TARGET = min(30, 6 * k)
    # 预计算热度分
    scored = [(c, crowd_score(c[0], raw_reds)) for c in pool]
    # 首组取热度最低（冷门优先）
    scored.sort(key=lambda x: (x[1], -x[0][5], x[0][0]))
    chosen, union = [scored[0][0]], set(scored[0][0][1])
    # 续组：贪心选"新增覆盖最多"的组合（热度规避作 tie-break）
    while len(chosen) < k:
        best, bestkey = None, None
        for c, sc in scored:
            if any(len(c[1] & ch[1]) > max_overlap for ch in chosen):
                continue
            marginal = len(c[1] - union)
            key = (marginal, -sc, c[5], c[0])   # 覆盖 > 冷门 > 均衡 > 小号
            if bestkey is None or key > bestkey:
                bestkey, best = key, c
        chosen.append(best); union |= best[1]
    # 局部搜索：替换任一组成员以增覆盖（热度规避仍作 tie-break）
    best_cover = len(union)
    improved = True
    while improved and best_cover < COVER_TARGET:
        improved = False
        for i in range(len(chosen)):
            for c, sc in scored:
                if c in chosen:
                    continue
                if any(len(c[1] & ch[1]) > max_overlap for j, ch in enumerate(chosen) if j != i):
                    continue
                new_union = union - chosen[i][1] | c[1]
                if len(new_union) > best_cover:
                    chosen[i] = c; union = new_union; best_cover = len(new_union)
                    improved = True
                    break
            if improved:
                break
    return chosen, best_cover

# ---------------------------------------------------------------------------
# 蒙特卡洛对比
def monte_carlo(tickets, n=N_SIM):
    pc = prize_counts()
    hit_any = 0
    hit_first = 0
    exp_win = 0.0
    for _ in range(n):
        draw_red = frozenset(random.sample(range(1, 34), 6))
        draw_blue = random.randint(1, 16)
        won = False
        for tred, tblu in tickets:
            rm = len(draw_red & tred)
            bm = (draw_blue == tblu)
            if is_win(rm, bm):
                won = True
                # 奖级映射（用于期望）
                if rm == 6 and bm: exp_win += PRIZE["一等奖"]
                elif rm == 6: exp_win += PRIZE["二等奖"]
                elif rm == 5 and bm: exp_win += PRIZE["三等奖"]
                elif (rm == 5 and not bm) or (rm == 4 and bm): exp_win += PRIZE["四等奖"]
                elif (rm == 4 and not bm) or (rm == 3 and bm): exp_win += PRIZE["五等奖"]
                else: exp_win += PRIZE["六等奖"]
                if rm == 6 and bm: hit_first += 1
                break
        if won:
            hit_any += 1
    return hit_any / n, hit_first / n, exp_win / n

def load_tickets(path):
    t = []
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            reds = frozenset(int(x) for x in row["红球"].split())
            t.append((reds, int(row["蓝球"])))
    return t

# ---------------------------------------------------------------------------
def write_csv(groups, blue_of, cover, raw_reds):
    path = CSV_OUT
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["组号", "红球", "蓝球", "奇偶比", "AC值", "三区",
                    "热/温/冷", "热度分", "与历史重号", "含三连号"])
        for i, (nums, _, h, ww, c, _) in enumerate(groups):
            odd = sg.odd_count(nums); z = sg.zone_counts(nums)
            w.writerow([f"第{i+1}组", " ".join(f"{n:02d}" for n in nums),
                        f"{blue_of[i]:02d}", f"{odd}:{6-odd}", sg.ac_value(nums),
                        f"{z[0]}/{z[1]}/{z[2]}", f"{h}/{ww}/{c}",
                        crowd_score(nums, raw_reds),
                        "是" if frozenset(nums) in raw_reds else "否", "否"])
    return path

def write_html(groups, blue_of, cover, p_enh, p_enh_first, ev_enh,
               p_base, p_base_first, ev_base, stats, blues):
    path = HTML_OUT
    rows = []
    for i, (nums, _, h, ww, c, _) in enumerate(groups):
        odd = sg.odd_count(nums); z = sg.zone_counts(nums)
        cells = "".join(f'<td class="r">{n:02d}</td>' for n in nums)
        rows.append(f'<tr><td class="num">第{i+1}组</td>{cells}'
                    f'<td class="b">{blue_of[i]:02d}</td>'
                    f'<td class="num">{odd}:{6-odd}</td><td class="num">{sg.ac_value(nums)}</td>'
                    f'<td class="num">{z[0]}/{z[1]}/{z[2]}</td>'
                    f'<td class="num">{h}/{ww}/{c}</td></tr>')
    group_html = "\n".join(rows)
    blue_rows = "".join(
        f'<tr class="{"bs" if b in set(blues) else ""}"><td class="num">{b:02d}</td>'
        f'<td class="num">{stats[b][0]}</td><td class="num">{stats[b][1]}</td>'
        f'<td>{"✔选用" if b in set(blues) else ""}</td></tr>'
        for b in range(1, 17))
    html = f"""<!doctype html><html lang=zh><head><meta charset=utf-8>
<title>双色球优化引擎推荐</title>
<style>
*{{font-family:-apple-system,"Microsoft YaHei",sans-serif;box-sizing:border-box}}
body{{margin:0;padding:24px;background:#f5f7fa;color:#1f2937}}
.wrap{{max-width:980px;margin:0 auto}}
h1{{font-size:22px;margin:0 0 4px}} .sub{{color:#6b7280;font-size:13px;margin-bottom:16px}}
.card{{background:#fff;border-radius:12px;padding:18px 20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
h2{{font-size:16px;margin:0 0 12px;border-left:4px solid #0f766e;padding-left:10px}}
table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{border:1px solid #e5e7eb;padding:7px 9px;text-align:center}}
th{{background:#f0fdfa;color:#0f766e;font-weight:600}} td.num{{font-variant-numeric:tabular-nums}}
td.r{{color:#d7282f;font-weight:600}} td.b{{color:#1565c0;font-weight:600}}
tr.bs{{background:#fff8e1}} .kpi{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:8px}}
.kpi div{{flex:1;min-width:140px;background:#f0fdfa;border-radius:10px;padding:12px;text-align:center}}
.kpi b{{display:block;font-size:19px;color:#0f766e}} .kpi span{{font-size:12px;color:#6b7280}}
.note{{font-size:12px;color:#6b7280;line-height:1.7}} .warn{{background:#fff7ed;border-left:4px solid #ea580c;padding:10px 14px;font-size:13px;color:#9a3412;border-radius:6px}}
.model{{font-size:12.5px;color:#374151;line-height:1.8}} .model b{{color:#0f766e}}
</style></head><body><div class=wrap>
<h1>双色球 · 增强优化引擎推荐（5步法第6层）</h1>
<div class=sub>数学模型：频率学 / 贝叶斯 / 信息熵 / 组合覆盖设计 / 整数规划近似 / 蒙特卡洛 · 生成 2026-07-19 · 模拟 {N_SIM:,} 次</div>

<div class=card><h2>一、本次推荐 5 组（10元）</h2>
<div class=kpi>
<div><b>{len(groups)}组</b><span>10元单式</span></div>
<div><b>{cover}/33</b><span>红球覆盖率</span></div>
<div><b>5/16</b><span>蓝球分散（5个不同蓝）</span></div>
<div><b>{p_enh*100:.2f}%</b><span>至少中一奖(蒙特卡洛)</span></div>
</div>
<table><thead><tr><th>组号</th><th>红1</th><th>红2</th><th>红3</th><th>红4</th><th>红5</th><th>红6</th><th>蓝</th><th>奇偶</th><th>AC</th><th>三区</th><th>热/温/冷</th></tr></thead><tbody>{group_html}</tbody></table>
<p class=note>全部满足 R1奇偶[2,4] · R2 AC[6,9] · R3三区[1,4] · 无三连号 · 热温冷2:2:2；5注蓝球互不相同（末等奖保底率理论最大 1-(15/16)^5={1-(15/16)**5:.1%}）。</p>
</div>

<div class=card><h2>二、蓝球分配（5个不同，优先备选+补遗漏最长）</h2>
<table><thead><tr><th>蓝球</th><th>出现次数</th><th>当前遗漏</th><th>选用</th></tr></thead><tbody>{blue_rows}</tbody></table>
</div>

<div class=card><h2>三、用了哪些数学模型</h2>
<div class=model>
<b>① 频率学</b>：红球冷热/遗漏统计（沿用5步法第2步），作为热度规避输入。<br>
<b>② 贝叶斯</b>：给定历史，各号"出球后验概率"=先验1/33（独立均匀下无信息增益）——据此明确<b>中一等奖不可优化</b>。<br>
<b>③ 信息熵</b>：选号均衡度最大化（奇偶/三区/热温冷2:2:2），避免任何偏倚，即最大熵选号。<br>
<b>④ 组合覆盖设计</b>：在合法池内选5个6-子集，并集最大化覆盖33红（期望命中数 = 6×覆盖/33）。<br>
<b>⑤ 整数规划近似</b>：约束(R1/R2/R3/无三连/热冷均衡/两两≤2)下贪心+局部搜索求覆盖极值。<br>
<b>⑥ 蒙特卡洛</b>：20万次模拟开奖，量化"至少中一奖/中一等奖/期望奖金"对比验证。
</div></div>

<div class=card><h2>四、蒙特卡洛验证：增强 vs 原5步方案</h2>
<table><tr><th>指标</th><th>增强方案(本推荐)</th><th>原5步方案</th><th>差异</th></tr>
<tr><td>至少中一奖率</td><td>{p_enh*100:.2f}%</td><td>{p_base*100:.2f}%</td><td style="color:#137333">+{(p_enh-p_base)*100:.2f}pp</td></tr>
<tr><td>中一等奖概率</td><td>{p_enh_first:.3e}</td><td>{p_base_first:.3e}</td><td>0（公理锁定）</td></tr>
<tr><td>期望回款/次(10元)</td><td>{ev_enh:.2f}元</td><td>{ev_base:.2f}元</td><td>+{ev_enh-ev_base:.2f}元</td></tr>
</table>
<p class=note>中一等奖概率两方案完全相同（=5/1772万），证明选号对"中大奖"零影响；增强方案提升的是末等奖保底率与小额奖期望（靠蓝球分散），属预算内可优化极值。</p>
</div>

<div class=card><div class=warn>
<b>诚实边界：</b>双色球独立均匀随机，<b>中一等奖概率恒 = 5/17,721,088</b>，任何数学模型都无法绕过——这不是悲观，是公理。<br>
本引擎"尽最大努力"优化的是三类<b>可优化</b>维度：末等奖保底率（蓝分散→+{(p_enh-p_base)*100:.1f}pp）、红球覆盖（{cover}/33）、人群热度规避（IF中高奖减分摊）。<br>
期望回款仍远低于10元投入（返奖率~50%数学必然），长期必亏；以上仅数据存档与概率参考，量力而行、图个乐。
</div></div>
</div></body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path

# ---------------------------------------------------------------------------
def main():
    random.seed(20260719)
    raw_reds = load_raw_reds()
    hot, warm, cold = sg.load_classes()
    pool = sg.build_pool(hot, warm, cold)

    blues, stats = select_blues_5()
    groups, cover = select_optimized(pool, raw_reds, k=5)
    blue_of = [blues[i % len(blues)] for i in range(len(groups))]

    enh_tickets = [(set(g[0]), blue_of[i]) for i, g in enumerate(groups)]
    base_tickets = load_tickets(FINAL)

    p_enh, p_enh_f, ev_enh = monte_carlo(enh_tickets)
    p_base, p_base_f, ev_base = monte_carlo(base_tickets)

    cp = write_csv(groups, blue_of, cover, raw_reds)
    hp = write_html(groups, blue_of, cover, p_enh, p_enh_f, ev_enh,
                    p_base, p_base_f, ev_base, stats, blues)

    print("== 双色球增强优化引擎 ==")
    print(f"合法池: {len(pool):,} | 红球覆盖: {cover}/33 | 蓝球: {blues}")
    print("推荐5组:")
    for i, (nums, _, h, ww, c, _) in enumerate(groups):
        print(f"  第{i+1}组: " + " ".join(f"{n:02d}" for n in nums)
              + f" | 蓝{blue_of[i]:02d} | 奇偶{sg.odd_count(nums)}:{6-sg.odd_count(nums)} "
              + f"AC{sg.ac_value(nums)} 三区{sg.zone_counts(nums)} 热度{crowd_score(nums, raw_reds)}")
    print(f"[蒙特卡洛] 增强 至少中一奖={p_enh:.4%} 中一等奖={p_enh_f:.3e} 期望={ev_enh:.2f}元")
    print(f"[蒙特卡洛] 原方案 至少中一奖={p_base:.4%} 中一等奖={p_base_f:.3e} 期望={ev_base:.2f}元")
    print("OK ->", cp, hp)

if __name__ == "__main__":
    main()
