# -*- coding: utf-8 -*-
"""
双色球 · 轮换生成器（娱乐消费框架专用）
=====================================
用途：每次"想起来买"前跑一次，生成 5 组与历史已买不重复的红蓝组合。
      - 复用 ssq_select_groups 的合法池（R1奇偶/R2 AC/R3三区/无三连号/热温冷2:2:2）
      - 额外约束：新组与历史任一组重复 ≤ 1 个（尽量避开已买号码，扩大长期覆盖）
      - 输出累计覆盖统计 + N次购买"至少中1次一等奖"概率表（诚实展示）

诚实声明：双色球独立随机，选号策略对中奖概率零影响。
          避重/换号不提升单期中奖概率，仅优化"覆盖感"与"新鲜感"体验，
          并避免"以为买了很多其实重复买同一组"的认知偏差。
          10元×低频 = 把亏损控制到可忽略的娱乐消费，同时保留"中一次就回本"的纯粹可能。
"""
import csv, os, math
import ssq_select_groups as sg

def _resolve_data_dir(env_name="SSQ_DATA"):
    # 兼容 Windows + Git Bash: os.getcwd()/环境变量可能返回 /x/... 形式的 POSIX 路径,
    # Windows 原生 Python 会误判为 C:/x/... 而找不到目录, 这里归一化为 X:/...
    p = os.environ.get(env_name, os.getcwd())
    if os.name == "nt" and len(p) >= 3 and p[0] == "/" and p[1].isalpha() and p[2] == "/":
        p = p[1].upper() + ":" + p[2:]
    return p

OUT = _resolve_data_dir("SSQ_DATA")
LOG = os.path.join(OUT, "ssq_play_log.csv")
RED_COMB = math.comb(33, 6)
TOTAL = RED_COMB * 16  # 17,721,088

# ---------------------------------------------------------------------------
def load_history():
    if not os.path.exists(LOG):
        return []
    hist = []
    with open(LOG, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            reds = tuple(int(x) for x in row["红球"].split())
            hist.append((row["日期"], reds, int(row["蓝"])))
    return hist

def save_history(hist):
    with open(LOG, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["日期", "红球", "蓝"])
        for d, reds, b in hist:
            w.writerow([d, " ".join(f"{n:02d}" for n in reds), f"{b:02d}"])

# ---------------------------------------------------------------------------
def gen_new_groups(pool, hist, k=5, max_overlap_hist=1, max_overlap_inner=2):
    hist_sets = [frozenset(r) for _, r, _ in hist]
    pool_sorted = sorted(pool, key=lambda c: (c[5], c[0]), reverse=True)
    chosen, union = [], set()
    # 首组：优先与历史重复≤1
    for c in pool_sorted:
        if all(len(c[1] & h) <= max_overlap_hist for h in hist_sets):
            chosen.append(c); union |= c[1]; break
    if not chosen:
        chosen.append(pool_sorted[0]); union |= chosen[0][1]
    # 续组：与历史≤1 且 组内两两≤2
    while len(chosen) < k:
        best, bestkey = None, None
        for c in pool:
            if any(len(c[1] & h) > max_overlap_hist for h in hist_sets):
                continue
            if any(len(c[1] & ch[1]) > max_overlap_inner for ch in chosen):
                continue
            key = (len(c[1] - union), c[5], c[0])
            if bestkey is None or key > bestkey:
                bestkey, best = key, c
        if best is None:  # 放宽历史约束
            for c in pool:
                if any(len(c[1] & ch[1]) > max_overlap_inner for ch in chosen):
                    continue
                key = (len(c[1] - union), c[5], c[0])
                if bestkey is None or key > bestkey:
                    bestkey, best = key, c
        chosen.append(best); union |= best[1]
    return chosen

# ---------------------------------------------------------------------------
def write_csv(groups, blue_of, hist):
    path = os.path.join(OUT, "ssq_rotate_groups.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["组号", "红球", "蓝球", "奇偶比", "AC值", "三区",
                    "热/温/冷", "与历史最大重复数", "含三连号"])
        all_hist = [frozenset(r) for _, r, _ in hist]
        for i, (nums, _, h, ww, c, _) in enumerate(groups):
            odd = sg.odd_count(nums); z = sg.zone_counts(nums)
            ov = max((len(set(nums) & hh) for hh in all_hist), default=0)
            w.writerow([f"第{i+1}组", " ".join(f"{n:02d}" for n in nums),
                        f"{blue_of[i]:02d}", f"{odd}:{6-odd}", sg.ac_value(nums),
                        f"{z[0]}/{z[1]}/{z[2]}", f"{h}/{ww}/{c}", ov, "否"])
    return path

def write_html(groups, blue_of, hist, cover_red, cover_blue, p_table):
    path = os.path.join(OUT, "双色球轮换选号.html")
    n_hist = len(hist)
    # 组合表
    rows = []
    all_hist = [frozenset(r) for _, r, _ in hist]
    for i, (nums, _, h, ww, c, _) in enumerate(groups):
        odd = sg.odd_count(nums); z = sg.zone_counts(nums)
        ov = max((len(set(nums) & hh) for hh in all_hist), default=0)
        cells = "".join(f'<td class="r">{n:02d}</td>' for n in nums)
        rows.append(f'<tr><td class="num">第{i+1}组</td>{cells}'
                    f'<td class="b">{blue_of[i]:02d}</td>'
                    f'<td class="num">{odd}:{6-odd}</td><td class="num">{sg.ac_value(nums)}</td>'
                    f'<td class="num">{z[0]}/{z[1]}/{z[2]}</td>'
                    f'<td class="num">{h}/{ww}/{c}</td>'
                    f'<td class="num" style="color:{"#137333" if ov<=1 else "#d7282f"}">{ov}</td><td>否</td></tr>')
    group_html = "\n".join(rows)
    # 概率表
    p_rows = []
    for N, p in p_table:
        p_rows.append(f'<tr><td class="num">{N}</td>'
                      f'<td class="num">{p*100:.4f}%</td>'
                      f'<td class="num">{p*10:.2f} 元</td>'
                      f'<td class="num">1/{1/p:.0f}</td></tr>')
    p_html = "\n".join(p_rows)
    hist_html = ("（暂无记录，本次为初始生成）" if n_hist == 0
                 else f"已记录 {n_hist} 次购买，累计覆盖红球 {cover_red}/33、蓝球 {cover_blue}/16")

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>双色球轮换选号（娱乐框架）</title>
<style>
*{{font-family:-apple-system,"Microsoft YaHei",sans-serif;box-sizing:border-box}}
body{{margin:0;padding:24px;background:#f5f7fa;color:#1f2d3d}}
h1{{font-size:22px;margin:0 0 4px}} .sub{{color:#6b7785;font-size:13px;margin-bottom:16px}}
.card{{background:#fff;border-radius:10px;padding:18px 20px;margin-bottom:18px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.card h2{{font-size:16px;margin:0 0 12px;border-left:4px solid #d7282f;padding-left:10px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border:1px solid #e4e8ee;padding:6px 8px;text-align:center}}
th{{background:#f0f3f7;font-weight:600}} td.num{{font-variant-numeric:tabular-nums}}
td.r{{color:#d7282f;font-weight:600}} td.b{{color:#1565c0;font-weight:600}}
.kpis{{display:flex;gap:14px;flex-wrap:wrap}} .kpi{{background:#f0f3f7;border-radius:8px;padding:10px 14px;flex:1;min-width:120px}}
.kpi b{{font-size:20px;color:#d7282f;display:block}} .kpi span{{font-size:12px;color:#6b7785}}
.note{{font-size:12px;color:#8a94a6;margin-top:14px;line-height:1.7}}
.badge{{display:inline-block;padding:3px 10px;border-radius:12px;background:#e6f4ea;color:#137333;font-weight:600;font-size:13px}}
</style></head><body>
<h1>双色球 · 轮换选号（娱乐消费框架）</h1>
<div class="sub">数据源：中彩网 · 窗口：第2026062~2026081期(20期) · 生成日期：2026-07-19</div>

<div class="card"><h2>本次 5 组（与历史已买不重复）</h2>
<div class="kpis">
<div class="kpi"><b>{len(groups)}组</b><span>本次生成 · 10元</span></div>
<div class="kpi"><b>{cover_red}/33</b><span>累计覆盖红球</span></div>
<div class="kpi"><b>{cover_blue}/16</b><span>累计覆盖蓝球</span></div>
<div class="kpi"><b>{n_hist}次</b><span>历史购买记录</span></div>
</div>
<p class="note">{hist_html}。新组与历史任一组重复均 ≤ 1 个（绿色），扩大长期覆盖空间。</p>
<table><thead><tr><th>组号</th><th>红1</th><th>红2</th><th>红3</th><th>红4</th><th>红5</th><th>红6</th><th>蓝</th><th>奇偶</th><th>AC</th><th>三区</th><th>热/温/冷</th><th>与历史重复</th><th>三连号</th></tr></thead><tbody>{group_html}</tbody></table>
</div>

<div class="card"><h2>"只需中1次" · 诚实概率表</h2>
<p class="note">单注一等奖概率 = 1/{TOTAL:,}；每次买5注不同单式，N次独立购买"至少中1次一等奖"概率如下。这仅是数学现实，不预示任何一期结果。</p>
<table><thead><tr><th>购买次数 N</th><th>至少中1次概率</th><th>累计投入(10元/次)</th><th>约等于 1/X</th></tr></thead><tbody>{p_html}</tbody></table>
</div>

<p class="note">⚠️ 双色球每期开奖为独立随机事件，历史号码与冷热/奇偶/AC/三区等指标均不预示未来。
轮换换号<b>不提升</b>单期中奖概率，仅优化覆盖感与体验、避免重复买同一组。
以上全部为数据存档与统计参考，<b>不构成任何购彩建议</b>。量力而行，图个乐就好。</p>
</body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path

# ---------------------------------------------------------------------------
def main():
    rows = sg.load_raw()
    hot, warm, cold = sg.load_classes()
    pool = sg.build_pool(hot, warm, cold)
    hist = load_history()

    new_groups = gen_new_groups(pool, hist, k=5)
    # 蓝球：复用第4步4个备选轮流
    stats = sg.blue_stats(rows)
    candidates, _, _, _ = sg.select_blues(stats)
    blue_of = [candidates[i % len(candidates)] for i in range(len(new_groups))]

    # 累计覆盖
    cover_red = set()
    cover_blue = set()
    for _, reds, b in hist:
        cover_red |= set(reds); cover_blue.add(b)
    for g, b in zip(new_groups, blue_of):
        cover_red |= set(g[0]); cover_blue.add(b)

    # 概率表
    p1 = 5.0 / TOTAL
    p_table = []
    for N in [1, 5, 10, 50, 100, 500, 1000]:
        p_at_least = 1 - (1 - p1) ** N
        p_table.append((N, p_at_least))

    cp = write_csv(new_groups, blue_of, hist)
    hp = write_html(new_groups, blue_of, hist, len(cover_red), len(cover_blue), p_table)

    print("== 双色球轮换生成器 ==")
    print(f"合法池: {len(pool):,} | 历史购买: {len(hist)} 次")
    print(f"累计覆盖红球 {len(cover_red)}/33, 蓝球 {len(cover_blue)}/16")
    print("本次5组:")
    for i, (nums, _, h, ww, c, _) in enumerate(new_groups):
        print(f"  第{i+1}组: " + " ".join(f"{n:02d}" for n in nums)
              + f" | 蓝{blue_of[i]:02d} | 奇偶{sg.odd_count(nums)}:{6-sg.odd_count(nums)} "
              + f"AC{sg.ac_value(nums)} 三区{sg.zone_counts(nums)} 热{h}温{ww}冷{c}")

if __name__ == "__main__":
    main()
