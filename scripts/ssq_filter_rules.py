# -*- coding: utf-8 -*-
"""
双色球(2026062-2026081, 20期) 硬性选号过滤规则 —— 奇偶比 / AC值 / 三区分布
================================================================================
数据源 : ssq_raw_20.csv (单一数据源, 源自中彩网官方)
规则属性: 自定义约束 (双色球官方无奇偶/AC/分区规则), 仅作统计过滤, 不构成选号建议

R1 奇偶比   : 红球奇数个数 ∈ [2,4]  → 允许 2:4 / 3:3 / 4:2; 剔除 1:5 / 5:1 / 0:6 / 6:0
R2 AC值     : ∈ [6,9]             → 剔除过度聚集(<6) 与过度离散(>9)
R3 三区分布 : 三区(01-11 / 12-22 / 23-33)每区出号数 ∈ [1,4] → 全覆盖且单区不超4(防扎堆)
"""
import csv
import os
from collections import Counter

OUT_DIR = os.environ.get("SSQ_DATA", os.getcwd())
RAW_CSV = os.path.join(OUT_DIR, "ssq_raw_20.csv")

# ---- 规则阈值 (集中定义, 便于后续调整) ----
ODD_MIN, ODD_MAX = 2, 4
AC_MIN, AC_MAX = 6, 9
ZONE_MIN, ZONE_MAX = 1, 4
ZONE_BOUNDS = [(1, 11), (12, 22), (23, 33)]  # 一区 / 二区 / 三区


def ac_value(nums):
    """AC值 = 两两差值去重个数 - (号码数-1); 红球6个故减5"""
    diffs = set()
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            diffs.add(nums[j] - nums[i])
    return len(diffs) - (len(nums) - 1)


def zone_dist(nums):
    return [sum(1 for x in nums if lo <= x <= hi) for lo, hi in ZONE_BOUNDS]


# ---- 读取原始数据 ----
rows = []
with open(RAW_CSV, encoding="utf-8-sig") as f:
    r = csv.DictReader(f)
    for row in r:
        reds = [int(row[f"红{i}"]) for i in range(1, 7)]
        rows.append((row["期号"], row["开奖日期"], reds))
N = len(rows)
print(f"数据期数: {N}  (窗口 {rows[-1][0]} ~ {rows[0][0]})")

# ---- 逐期回测 ----
results = []
for pid, dt, reds in rows:
    odd = sum(1 for x in reds if x % 2 == 1)
    ac = ac_value(reds)
    z = zone_dist(reds)
    r1 = ODD_MIN <= odd <= ODD_MAX
    r2 = AC_MIN <= ac <= AC_MAX
    r3 = all(ZONE_MIN <= zi <= ZONE_MAX for zi in z)
    ok = r1 and r2 and r3
    results.append(dict(pid=pid, dt=dt, reds=reds, odd=odd, ac=ac, z=z,
                        r1=r1, r2=r2, r3=r3, ok=ok))

# ---- 效能统计 ----
sat_r1 = sum(1 for x in results if x["r1"])
sat_r2 = sum(1 for x in results if x["r2"])
sat_r3 = sum(1 for x in results if x["r3"])
sat_all = sum(1 for x in results if x["ok"])
print(f"R1 奇偶满足 {sat_r1}/{N} ({sat_r1/N*100:.0f}%)")
print(f"R2 AC满足   {sat_r2}/{N} ({sat_r2/N*100:.0f}%)")
print(f"R3 三区满足 {sat_r3}/{N} ({sat_r3/N*100:.0f}%)")
print(f"联合满足   {sat_all}/{N} ({sat_all/N*100:.0f}%)")

# 分布统计
odd_ratio_dist = Counter(f"{x['odd']}:{6-x['odd']}" for x in results)
ac_dist = Counter(x["ac"] for x in results)
zone_shape_dist = Counter(f"{x['z'][0]}-{x['z'][1]}-{x['z'][2]}" for x in results)

# ---- CSV 输出 ----
csv_path = os.path.join(OUT_DIR, "ssq_filter_rules.csv")
with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["期号", "开奖日期", "红球", "奇数个数", "奇偶比", "AC值",
                "一区(01-11)", "二区(12-22)", "三区(23-33)",
                "R1奇偶", "R2_AC", "R3三区", "综合合规"])
    for x in results:
        redstr = " ".join(f"{n:02d}" for n in x["reds"])
        w.writerow([x["pid"], x["dt"], redstr, x["odd"], f"{x['odd']}:{6-x['odd']}",
                    x["ac"], x["z"][0], x["z"][1], x["z"][2],
                    "✓" if x["r1"] else "✗",
                    "✓" if x["r2"] else "✗",
                    "✓" if x["r3"] else "✗",
                    "合规" if x["ok"] else "剔除"])
print(f"CSV -> {csv_path}")


# ============ HTML 报告 ============
def dist_table(counter, title):
    items = sorted(counter.items(), key=lambda kv: -kv[1])
    maxv = max(counter.values()) if counter else 1
    rows_html = []
    for k, v in items:
        pct = v / N * 100
        bw = v / maxv * 100
        rows_html.append(
            f'<tr><td class="num">{k}</td><td class="num">{v}</td>'
            f'<td class="num">{pct:.0f}%</td>'
            f'<td><div class="bar" style="width:{bw:.0f}%"></div></td></tr>'
        )
    return f'<h4>{title}</h4><table class="mini"><thead><tr><th>取值</th><th>期数</th><th>占比</th><th></th></tr></thead><tbody>{"".join(rows_html)}</tbody></table>'


def mark(b):
    return '<span class="ok">✓</span>' if b else '<span class="no">✗</span>'


detail_rows = ""
for x in results:
    cls = "pass" if x["ok"] else "fail"
    detail_rows += (
        f'<tr class="{cls}"><td class="num">{x["pid"]}</td>'
        f'<td>{x["dt"]}</td>'
        f'<td class="reds">{" ".join(f"{n:02d}" for n in x["reds"])}</td>'
        f'<td class="num">{x["odd"]}</td><td class="num">{x["odd"]}:{6-x["odd"]}</td>'
        f'<td class="num">{x["ac"]}</td>'
        f'<td class="num">{x["z"][0]}-{x["z"][1]}-{x["z"][2]}</td>'
        f'<td>{mark(x["r1"])}</td><td>{mark(x["r2"])}</td><td>{mark(x["r3"])}</td>'
        f'<td><b class="{"ok" if x["ok"] else "no"}">{"合规" if x["ok"] else "剔除"}</b></td></tr>\n'
    )

# 规则卡
rules_html = f"""
<div class="rule">
  <div class="rkey">R1</div>
  <div class="rbody"><b>奇偶比</b> — 红球奇数个数 ∈ [{ODD_MIN}, {ODD_MAX}]<br>
  <span class="dim">允许 2:4 / 3:3 / 4:2；剔除 1:5 / 5:1 / 0:6 / 6:0 等极端偏态</span></div>
</div>
<div class="rule">
  <div class="rkey">R2</div>
  <div class="rbody"><b>AC值</b> — 算术复杂度 ∈ [{AC_MIN}, {AC_MAX}]<br>
  <span class="dim">AC = 两两差值去重个数 − 5；剔除过度聚集(&lt;{AC_MIN})与过度离散(&gt;{AC_MAX})</span></div>
</div>
<div class="rule">
  <div class="rkey">R3</div>
  <div class="rbody"><b>三区分布</b> — 三区每区出号数 ∈ [{ZONE_MIN}, {ZONE_MAX}]<br>
  <span class="dim">三区划分 01-11 / 12-22 / 23-33（各11个，等距自定义）；要求全覆盖且单区不超4（防扎堆）</span></div>
</div>"""


def perf_bar(label, sat, total):
    pct = sat / total * 100
    color = "#27ae60" if pct >= 80 else ("#f39c12" if pct >= 50 else "#e74c3c")
    return (f'<div class="prow"><span class="pl">{label}</span>'
            f'<div class="ptrack"><div class="pfill" style="width:{pct:.0f}%;background:{color}"></div></div>'
            f'<span class="pv">{sat}/{total} ({pct:.0f}%)</span></div>')


perf_html = (
    perf_bar("R1 奇偶比", sat_r1, N)
    + perf_bar("R2 AC值", sat_r2, N)
    + perf_bar("R3 三区分布", sat_r3, N)
    + perf_bar("三规则联合", sat_all, N)
)

html = f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>双色球硬性选号过滤规则 (奇偶/AC/三区)</title>
<style>
 *{{box-sizing:border-box;font-family:-apple-system,"Microsoft YaHei",sans-serif}}
 body{{margin:0;background:#f5f7fa;color:#222;padding:24px}}
 .wrap{{max-width:1040px;margin:0 auto}}
 h1{{font-size:22px;margin:0 0 4px}}
 .sub{{color:#666;font-size:13px;margin-bottom:18px}}
 .card{{background:#fff;border-radius:10px;padding:18px 20px;margin-bottom:18px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
 .card h2{{font-size:16px;margin:0 0 12px;border-left:4px solid #d7282f;padding-left:10px}}
 .rule{{display:flex;gap:12px;align-items:flex-start;padding:10px 0;border-bottom:1px dashed #eee}}
 .rule:last-child{{border-bottom:0}}
 .rkey{{flex:0 0 38px;height:38px;background:#d7282f;color:#fff;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px}}
 .rbody{{font-size:13px;line-height:1.6}}
 .dim{{color:#888;font-size:12px}}
 .prow{{display:flex;align-items:center;gap:10px;margin:7px 0;font-size:13px}}
 .pl{{flex:0 0 110px;font-weight:600}}
 .ptrack{{flex:1;background:#eee;border-radius:4px;height:16px;overflow:hidden}}
 .pfill{{height:100%;border-radius:4px}}
 .pv{{flex:0 0 120px;text-align:right;color:#555}}
 table{{width:100%;border-collapse:collapse;font-size:13px}}
 th,td{{padding:6px 8px;border-bottom:1px solid #eee;text-align:center}}
 th{{background:#fafafa;color:#555}}
 td.num{{font-variant-numeric:tabular-nums}}
 td.reds{{color:#d7282f;font-weight:600;letter-spacing:1px}}
 tr.pass{{background:#f3fbf5}} tr.fail{{background:#fdf3f3}}
 .mini{{margin:6px 0 14px;font-size:12px}} .mini th,.mini td{{padding:4px 6px}}
 .bar{{background:linear-gradient(90deg,#d7282f,#ff9a9e);height:12px;border-radius:3px}}
 .ok{{color:#27ae60;font-weight:700}} .no{{color:#e74c3c;font-weight:700}}
 .note{{font-size:12px;color:#888;line-height:1.7}}
 .grid2{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}}
 @media(max-width:760px){{.grid2{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">
<h1>📊 双色球 硬性选号过滤规则</h1>
<div class="sub">统计窗口: 第 {rows[-1][0]}–{rows[0][0]} 期 ｜ 共 {N} 期 ｜ 回测验证 (规则均为自定义约束)</div>

<div class="card">
  <h2>① 规则定义</h2>
  {rules_html}
  <div class="note">⚠ 双色球官方无奇偶比 / AC值 / 分区规则，以上为自定义统计过滤约束，仅用于剔除历史中极端形态组合，<b>不构成任何选号建议</b>。</div>
</div>

<div class="card">
  <h2>② 规则过滤效能 (20期回测)</h2>
  {perf_html}
  <div class="note">联合满足率 = 同时过 R1+R2+R3 的期数占比；该值越低代表过滤越严格（剔除越多）。</div>
</div>

<div class="card">
  <h2>③ 20期形态分布</h2>
  <div class="grid2">
    <div>{dist_table(odd_ratio_dist, "奇偶比分布")}</div>
    <div>{dist_table(ac_dist, "AC值分布")}</div>
    <div>{dist_table(zone_shape_dist, "三区形态分布")}</div>
  </div>
</div>

<div class="card">
  <h2>④ 逐期回测明细</h2>
  <table><thead><tr><th>期号</th><th>日期</th><th>红球</th><th>奇数</th><th>奇偶比</th><th>AC</th><th>三区</th><th>R1</th><th>R2</th><th>R3</th><th>综合</th></tr></thead>
  <tbody>{detail_rows}</tbody></table>
</div>

<div class="card note">
  ⚠️ <b>理性购彩提示:</b> 双色球为完全随机的独立事件，每期开奖概率恒定。历史形态分布不预示未来，
  本套规则仅作数据归档与统计过滤描述，<b>不构成任何选号建议</b>。请量力而行，理性投注。
  <br>数据来源: 中彩网(zhcw.com)。存档文件: ssq_raw_20.csv, ssq_filter_rules.csv。
</div>
</div></body></html>'''

html_path = os.path.join(OUT_DIR, "双色球选号过滤规则.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"HTML -> {html_path}")
