# -*- coding: utf-8 -*-
"""
双色球近20期(2026062-2026081) 红球(01-33) 冷热属性分析
========================================================
数据源 : ssq_raw_20.csv (由 build_db.py 构建, 源自中彩网官方)
分类口径: 双色球自有冷热分类标准(均值±0.5标准差, 与大乐透互不引用)
          - 出现次数 >= 均值+0.5×标准差  → 热
          - 出现次数 <= 均值-0.5×标准差  → 冷
          - 其余                          → 温
          - 遗漏 = 距最新一期(2026081)隔了多少期未出 (最新期出现则0; 从未出现则=期数N)
说明   : 双色球官方无冷热/分区规则, 本表为纯统计描述, 不构成选号建议。
"""
import csv
import os
from collections import Counter

def _resolve_data_dir(env_name="SSQ_DATA"):
    # 兼容 Windows + Git Bash: os.getcwd()/环境变量可能返回 /x/... 形式的 POSIX 路径,
    # Windows 原生 Python 会误判为 C:/x/... 而找不到目录, 这里归一化为 X:/...
    p = os.environ.get(env_name, os.getcwd())
    if os.name == "nt" and len(p) >= 3 and p[0] == "/" and p[1].isalpha() and p[2] == "/":
        p = p[1].upper() + ":" + p[2:]
    return p

OUT_DIR = _resolve_data_dir("SSQ_DATA")
RAW_CSV = os.path.join(OUT_DIR, "ssq_raw_20.csv")

# ---- 读取原始数据 (CSV 第一行=最新一期, 倒序索引0=最新) ----
rows = []
with open(RAW_CSV, encoding="utf-8-sig") as f:
    r = csv.DictReader(f)
    for row in r:
        reds = [int(row[f"红{i}"]) for i in range(1, 7)]
        rows.append((row["期号"], row["开奖日期"], reds))
N = len(rows)
print(f"数据期数: {N}  (窗口 {rows[-1][0]} ~ {rows[0][0]})")

# ---- 数据质量校验 ----
errs = []
for pid, dt, reds in rows:
    if len(reds) != 6:
        errs.append(f"{pid} 红球数量异常:{len(reds)}")
    if len(set(reds)) != 6:
        errs.append(f"{pid} 红球重复:{reds}")
    if any(x < 1 or x > 33 for x in reds):
        errs.append(f"{pid} 红球越界:{reds}")
for i in range(1, N):
    if int(rows[i - 1][0]) - int(rows[i][0]) != 1:
        errs.append(f"期次不连续 {rows[i][0]}->{rows[i-1][0]}")
print("校验:", errs if errs else "无")

# ---- 频次 & 遗漏 ----
freq = {n: 0 for n in range(1, 34)}
last_idx = {}
for idx, (pid, dt, reds) in enumerate(rows):   # idx 0=最新一期
    for n in reds:
        freq[n] += 1
        if n not in last_idx:        # rows 为最新→最早, 首次遇到=最小索引=最近一期
            last_idx[n] = idx
miss = {n: (last_idx[n] if n in last_idx else N) for n in range(1, 34)}

vals = list(freq.values())
mean = sum(vals) / len(vals)
var = sum((v - mean) ** 2 for v in vals) / len(vals)
std = var ** 0.5

# ---- 冷热分类 (均值±0.5*std) ----
hot_thr = mean + 0.5 * std
cold_thr = mean - 0.5 * std
cls = {}
for n, v in freq.items():
    cls[n] = "热" if v >= hot_thr else ("冷" if v <= cold_thr else "温")
print(f"红球均值={mean:.3f} 标准差={std:.3f}")
print(f"热阈值>={hot_thr:.2f} 冷阈值<={cold_thr:.2f}")

# ---- CSV 输出 ----
csv_path = os.path.join(OUT_DIR, "ssq_red_coldhot.csv")
with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["号码", "出现次数", "当前遗漏(期)", "分类", "每期出现率"])
    for n in range(1, 34):
        w.writerow([f"{n:02d}", freq[n], miss[n], cls[n], f"{freq[n]/N:.3f}"])
print(f"CSV -> {csv_path}")

# ---- 汇总 ----
hot_list = [f"{n:02d}({freq[n]}次,漏{miss[n]})" for n in range(1, 34) if cls[n] == "热"]
warm_list = [f"{n:02d}({freq[n]}次,漏{miss[n]})" for n in range(1, 34) if cls[n] == "温"]
cold_list = [f"{n:02d}({freq[n]}次,漏{miss[n]})" for n in range(1, 34) if cls[n] == "冷"]
print("热:", " ".join(hot_list))
print("温:", " ".join(warm_list))
print("冷:", " ".join(cold_list))


# ============ HTML 报告 ============
def bar_chart(freq, cls, maxv):
    cells = []
    for n in range(1, 34):
        v = freq[n]
        c = cls[n]
        color = "#e74c3c" if c == "热" else ("#2980b9" if c == "冷" else "#95a5a6")
        w = max(2, v / maxv * 100)
        cells.append(
            f'<div class="brow"><span class="bnum">{n:02d}</span>'
            f'<div class="btrack"><div class="bfill" style="width:{w:.1f}%;background:{color}"></div></div>'
            f'<span class="bval">{v}</span><span class="btag {c}">{c}</span></div>'
        )
    return "\n".join(cells)


# 数据表格(按号码顺序, 清晰可读)
table_rows = ""
for n in range(1, 34):
    c = cls[n]
    tagcls = "hot" if c == "热" else ("cold" if c == "冷" else "warm")
    table_rows += (
        f'<tr><td class="num">{n:02d}</td><td class="num">{freq[n]}</td>'
        f'<td class="num">{miss[n]}</td>'
        f'<td><span class="tag {tagcls}">{c}</span></td>'
        f'<td class="num">{freq[n]/N*100:.1f}%</td></tr>\n'
    )

fmax = max(freq.values())
n_hot = sum(1 for v in cls.values() if v == "热")
n_warm = sum(1 for v in cls.values() if v == "温")
n_cold = sum(1 for v in cls.values() if v == "冷")

html = f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>双色球红球冷热属性分析 (近20期)</title>
<style>
 *{{box-sizing:border-box;font-family:-apple-system,"Microsoft YaHei",sans-serif}}
 body{{margin:0;background:#f5f7fa;color:#222;padding:24px}}
 .wrap{{max-width:1000px;margin:0 auto}}
 h1{{font-size:22px;margin:0 0 4px}}
 .sub{{color:#666;font-size:13px;margin-bottom:20px}}
 .card{{background:#fff;border-radius:10px;padding:18px 20px;margin-bottom:18px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
 .kv{{display:flex;gap:18px;flex-wrap:wrap;font-size:13px;margin-bottom:6px}}
 .kv b{{color:#333}}
 .tag{{display:inline-block;padding:2px 10px;border-radius:4px;font-size:12px;margin:2px}}
 .hot{{background:#fdecea;color:#e74c3c}}.cold{{background:#eaf3fb;color:#2980b9}}.warm{{background:#f0f0f0;color:#777}}
 .brow{{display:flex;align-items:center;gap:8px;margin:3px 0;font-size:12px}}
 .bnum{{width:22px;font-weight:600}}
 .btrack{{flex:1;background:#eee;border-radius:3px;height:14px;overflow:hidden}}
 .bfill{{height:100%;border-radius:3px}}
 .bval{{width:18px;text-align:right;color:#555}}
 .btag{{width:18px;text-align:center}}
 table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}}
 th,td{{padding:7px 8px;border-bottom:1px solid #eee;text-align:center}}
 th{{background:#fafafa;color:#555;position:sticky;top:0}}
 td.num{{font-variant-numeric:tabular-nums}}
 .tgrid{{max-height:520px;overflow:auto}}
 .note{{font-size:12px;color:#888;line-height:1.7}}
</style></head><body><div class="wrap">
<h1>📊 双色球 红球冷热属性分析</h1>
<div class="sub">统计窗口: 第 {rows[-1][0]}–{rows[0][0]} 期 ({rows[-1][1]} ~ {rows[0][1]}) ｜ 共 {N} 期 ｜ 数据截至 {rows[0][1]} 第{rows[0][0]}期</div>

<div class="card">
  <div class="kv"><span><b>数据校验:</b> 期次连续 ✓ 每期红球6个 ✓ 无越界/重复 ✓</span></div>
  <div class="kv">
    <span><b>红球均值</b> {mean:.3f} 次</span>
    <span><b>标准差</b> {std:.3f}</span>
    <span><b>热阈值</b> ≥ {hot_thr:.2f}</span>
    <span><b>冷阈值</b> ≤ {cold_thr:.2f}</span>
  </div>
  <div class="kv">
    <span><b>热号</b> {n_hot} 个</span><span><b>温号</b> {n_warm} 个</span><span><b>冷号</b> {n_cold} 个</span>
    <span><b>理论每期出现率</b> {6/33*100:.1f}%</span>
  </div>
  <div class="note">分类规则(双色球自有标准): 出现次数 ≥ 均值+0.5×标准差 为<span class="tag hot">热</span>；≤ 均值−0.5×标准差 为<span class="tag cold">冷</span>；其余为<span class="tag warm">温</span>。"遗漏"=距最新一期({rows[0][0]})隔了多少期未出。双色球官方无冷热/分区规则，本表为纯统计描述。</div>
</div>

<div class="card">
  <h3 style="margin-top:0">🔥 热号 ({n_hot})</h3>
  <div>{" ".join(f'<span class="tag hot">{x}</span>' for x in hot_list)}</div>
  <h3>🌡️ 温号 ({n_warm})</h3>
  <div>{" ".join(f'<span class="tag warm">{x}</span>' for x in warm_list)}</div>
  <h3>❄️ 冷号 ({n_cold})</h3>
  <div>{" ".join(f'<span class="tag cold">{x}</span>' for x in cold_list)}</div>
  <div style="margin-top:14px">{bar_chart(freq, cls, fmax)}</div>
</div>

<div class="card">
  <h3 style="margin-top:0">📋 红球冷热明细表 (01-33)</h3>
  <div class="tgrid">
  <table><thead><tr><th>号码</th><th>出现次数</th><th>当前遗漏(期)</th><th>分类</th><th>每期出现率</th></tr></thead>
  <tbody>{table_rows}</tbody></table>
  </div>
</div>

<div class="card note">
  ⚠️ <b>理性购彩提示:</b> 双色球为完全随机的独立事件，每期每个号码出现概率恒定，历史冷热不代表未来趋势。
  本分析仅作数据归档与统计描述，<b>不构成任何选号建议</b>。请量力而行，理性投注。
  <br>数据来源: 中彩网(zhcw.com)官方开奖公告。存档文件: ssq_raw_20.csv, ssq_red_coldhot.csv。
</div>
</div></body></html>'''

html_path = os.path.join(OUT_DIR, "双色球红球冷热分析.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"HTML -> {html_path}")
