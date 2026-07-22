# -*- coding: utf-8 -*-
"""
双色球近20期号码数据库构建脚本（可复现 · 离线友好）
================================================
数据源 : 中彩网 https://www.zhcw.com/kjxx/ssq/ （中国福利彩票官方权威发布）
内置样本窗口: 第2026062期 ~ 第2026081期（共20期，2026-07-19 抓取，离线可复现）

双色球规则: 每期红球6个(01-33) + 蓝球1个(01-16)；每周二/四/日开奖。

用法（数据来源优先级）:
  python build_db.py                  # 默认：复用本地 ssq_raw_20.csv；不存在则用内置样本
  python build_db.py --from-csv X.csv # 用用户提供的近20期CSV（列: 期号,开奖日期,红1..红6,蓝）
  python build_db.py --fetch          # 实验性：联网抓取中彩网最新20期（解析失败自动回退内置样本）

产出文件（写入当前工作目录，或用环境变量 SSQ_DATA 指定）:
  - ssq_raw_20.csv        原始号码数据库（单一数据源）
  - 双色球数据库.html      可视化浏览 + 数据质量校验 + 频次统计
  - summary.json          机器可读摘要

免责声明: 双色球每期开奖为独立随机事件，历史号码不预示未来，
          本数据库仅作数据存档与统计分析之用，不构成任何购彩建议。
"""

import csv
import json
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import datetime

OUT_DIR = os.environ.get("SSQ_DATA", os.getcwd())

# ---------------------------------------------------------------------------
# 1) 原始抓取数据（来自中彩网官方页面，2026-07-19 实时抓取）
#    字段: (期号, 开奖日期, 红1, 红2, 红3, 红4, 红5, 红6, 蓝)
# ---------------------------------------------------------------------------
RAW = [
    ("2026081", "2026-07-16", "06", "10", "12", "15", "24", "27", "12"),
    ("2026080", "2026-07-14", "04", "05", "11", "19", "27", "32", "01"),
    ("2026079", "2026-07-12", "01", "11", "17", "22", "24", "29", "04"),
    ("2026078", "2026-07-09", "07", "11", "14", "16", "27", "28", "06"),
    ("2026077", "2026-07-07", "01", "04", "05", "14", "18", "25", "04"),
    ("2026076", "2026-07-05", "01", "03", "19", "20", "24", "25", "07"),
    ("2026075", "2026-07-02", "08", "12", "18", "21", "24", "30", "01"),
    ("2026074", "2026-06-30", "02", "23", "24", "26", "28", "32", "04"),
    ("2026073", "2026-06-28", "09", "10", "13", "16", "19", "21", "08"),
    ("2026072", "2026-06-25", "07", "08", "12", "15", "17", "21", "01"),
    ("2026071", "2026-06-23", "03", "08", "19", "25", "31", "33", "05"),
    ("2026070", "2026-06-21", "03", "06", "08", "14", "26", "27", "08"),
    ("2026069", "2026-06-18", "12", "14", "16", "17", "18", "32", "08"),
    ("2026068", "2026-06-16", "03", "05", "16", "18", "29", "32", "04"),
    ("2026067", "2026-06-14", "04", "19", "27", "29", "30", "32", "13"),
    ("2026066", "2026-06-11", "05", "11", "21", "23", "24", "29", "16"),
    ("2026065", "2026-06-09", "07", "08", "16", "24", "30", "32", "02"),
    ("2026064", "2026-06-07", "01", "09", "15", "18", "29", "33", "15"),
    ("2026063", "2026-06-04", "02", "08", "25", "28", "30", "31", "02"),
    ("2026062", "2026-06-02", "02", "04", "07", "14", "28", "29", "09"),
]

EXPECTED_DRAW_WEEKDAYS = {1, 3, 6}  # 周二(1) / 周四(3) / 周日(6)


def parse_row(row):
    period = row[0]
    date_str = row[1]
    reds = list(row[2:8])
    blue = row[8]
    return period, date_str, reds, blue


def validate(rows):
    """数据质量校验，返回 (passed, issues)"""
    issues = []

    # 期号连续递减且数量=20
    periods = [r[0] for r in rows]
    if len(periods) != 20:
        issues.append(f"期数不为20，实际={len(periods)}")
    for i in range(1, len(periods)):
        prev = int(periods[i - 1])
        cur = int(periods[i])
        if prev - cur != 1:
            issues.append(f"期号不连续: {periods[i-1]} -> {periods[i]}")

    # 每期号码规则
    for r in rows:
        period, date_str, reds, blue = parse_row(r)
        # 红球
        if len(reds) != 6:
            issues.append(f"{period}: 红球数量异常={len(reds)}")
        try:
            rints = [int(x) for x in reds]
        except ValueError:
            issues.append(f"{period}: 红球含非数字 {reds}")
            rints = []
        if rints:
            if any(n < 1 or n > 33 for n in rints):
                issues.append(f"{period}: 红球超出01-33范围 {reds}")
            if len(set(rints)) != len(rints):
                issues.append(f"{period}: 红球存在重复 {reds}")
            if rints != sorted(rints):
                issues.append(f"{period}: 红球未升序排列 {reds}")
        # 蓝球
        try:
            bint = int(blue)
        except ValueError:
            issues.append(f"{period}: 蓝球非数字 {blue}")
            bint = -1
        if bint != -1:
            if bint < 1 or bint > 16:
                issues.append(f"{period}: 蓝球超出01-16范围 {blue}")

        # 日期与星期
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
            if d.weekday() not in EXPECTED_DRAW_WEEKDAYS:
                issues.append(f"{period}: 开奖日非周二/四/日 {date_str}(周{d.weekday()})")
        except ValueError:
            issues.append(f"{period}: 日期格式异常 {date_str}")

    # 相邻期间隔天数合理性（2~4天）
    for i in range(1, len(rows)):
        d1 = datetime.strptime(rows[i - 1][1], "%Y-%m-%d")
        d0 = datetime.strptime(rows[i][1], "%Y-%m-%d")
        gap = (d1 - d0).days
        if gap < 2 or gap > 4:
            issues.append(f"{rows[i][0]}: 与上一期间隔异常 {gap}天")

    return (len(issues) == 0, issues)


def build_frequency(rows):
    red_counter = Counter()
    blue_counter = Counter()
    for r in rows:
        _, _, reds, blue = parse_row(r)
        for x in reds:
            red_counter[int(x)] += 1
        blue_counter[int(blue)] += 1
    red_freq = {str(n).zfill(2): red_counter.get(n, 0) for n in range(1, 34)}
    blue_freq = {str(n).zfill(2): blue_counter.get(n, 0) for n in range(1, 17)}
    return red_freq, blue_freq


def write_csv(rows):
    path = os.path.join(OUT_DIR, "ssq_raw_20.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["期号", "开奖日期", "红1", "红2", "红3", "红4", "红5", "红6", "蓝"])
        for r in rows:
            w.writerow(r)
    return path


def write_html(rows, red_freq, blue_freq, passed, issues):
    path = os.path.join(OUT_DIR, "双色球数据库.html")

    # 频次条形
    def bar_table(freq, maxv):
        rows_html = []
        for k, v in freq.items():
            pct = (v / maxv * 100) if maxv else 0
            rows_html.append(
                f'<tr><td class="num">{k}</td>'
                f'<td class="num">{v}</td>'
                f'<td><div class="bar" style="width:{pct:.1f}%"></div></td></tr>'
            )
        return "\n".join(rows_html)

    max_red = max(red_freq.values()) or 1
    max_blue = max(blue_freq.values()) or 1

    data_rows = []
    for r in rows:
        period, date_str, reds, blue = parse_row(r)
        red_cells = "".join(f'<td class="r">{x}</td>' for x in reds)
        data_rows.append(
            f'<tr><td class="num">{period}</td><td>{date_str}</td>'
            f'{red_cells}<td class="b">{blue}</td></tr>'
        )
    data_html = "\n".join(data_rows)

    status = "校验通过 ✅" if passed else "校验未通过 ❌"
    issues_html = (
        "<ul>" + "".join(f"<li>{i}</li>" for i in issues) + "</ul>"
        if issues else "<p>无异常</p>"
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>双色球近20期号码数据库</title>
<style>
*{{font-family:-apple-system,"Microsoft YaHei",sans-serif;box-sizing:border-box}}
body{{margin:0;padding:24px;background:#f5f7fa;color:#1f2d3d}}
h1{{font-size:22px;margin:0 0 4px}}
.sub{{color:#6b7785;font-size:13px;margin-bottom:20px}}
.card{{background:#fff;border-radius:10px;padding:18px 20px;margin-bottom:18px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.card h2{{font-size:16px;margin:0 0 12px;border-left:4px solid #d7282f;padding-left:10px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border:1px solid #e4e8ee;padding:6px 8px;text-align:center}}
th{{background:#f0f3f7;font-weight:600}}
td.num{{font-variant-numeric:tabular-nums}}
td.r{{color:#d7282f;font-weight:600}}
td.b{{color:#1565c0;font-weight:600}}
.bar{{background:linear-gradient(90deg,#d7282f,#ff7a7f);height:14px;border-radius:3px}}
.freq td.num{{text-align:center}}
.badge{{display:inline-block;padding:4px 12px;border-radius:14px;font-weight:600;font-size:14px}}
.ok{{background:#e6f4ea;color:#137333}}
.no{{background:#fce8e8;color:#c5221f}}
.note{{font-size:12px;color:#8a94a6;margin-top:14px;line-height:1.6}}
</style></head><body>
<h1>双色球近20期号码数据库</h1>
<div class="sub">数据源：中彩网(zhcw.com) · 构建日期：2026-07-19 · 窗口：第2026062期 ~ 第2026081期</div>

<div class="card">
  <h2>数据质量校验</h2>
  <p>状态：<span class="badge {'ok' if passed else 'no'}">{status}</span></p>
  {issues_html}
</div>

<div class="card">
  <h2>原始开奖号码（按最新→最早）</h2>
  <table>
    <thead><tr><th>期号</th><th>开奖日期</th><th>红1</th><th>红2</th><th>红3</th><th>红4</th><th>红5</th><th>红6</th><th>蓝</th></tr></thead>
    <tbody>{data_html}</tbody>
  </table>
</div>

<div class="card">
  <h2>红球频次（01-33，共{len(rows)*6}次出现）</h2>
  <table class="freq"><thead><tr><th>号码</th><th>出现</th><th>分布</th></tr></thead>
  <tbody>{bar_table(red_freq, max_red)}</tbody></table>
</div>

<div class="card">
  <h2>蓝球频次（01-16，共{len(rows)}次出现）</h2>
  <table class="freq"><thead><tr><th>号码</th><th>出现</th><th>分布</th></tr></thead>
  <tbody>{bar_table(blue_freq, max_blue)}</tbody></table>
</div>

<p class="note">⚠️ 双色球每期开奖为独立随机事件，历史号码不预示未来，本数据库仅作数据存档与统计分析之用，不构成任何购彩建议。</p>
</body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def write_summary(rows, red_freq, blue_freq, passed, issues):
    path = os.path.join(OUT_DIR, "summary.json")
    summary = {
        "lottery": "双色球",
        "source": "中彩网 https://www.zhcw.com/kjxx/ssq/",
        "build_date": "2026-07-19",
        "period_range": [rows[-1][0], rows[0][0]],
        "period_count": len(rows),
        "latest_period": rows[0][0],
        "latest_date": rows[0][1],
        "data_quality": {
            "passed": passed,
            "issues": issues,
            "checks": [
                "期号连续(2026062-2026081)",
                "红球6个且01-33无重复升序",
                "蓝球1个且01-16",
                "开奖日为周二/四/日",
                "相邻期间隔2-4天",
            ],
        },
        "red_frequency": red_freq,
        "blue_frequency": blue_freq,
        "disclaimer": "开奖随机，历史不预示未来，仅供数据存档与统计分析。",
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return path


def load_from_csv(path):
    """从用户CSV(列: 期号,开奖日期,红1..红6,蓝)读取，最新一期在前。"""
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            reds = [str(r[f"红{i}"]).zfill(2) for i in range(1, 7)]
            rows.append([str(r["期号"]), str(r["开奖日期"]), *reds, str(r["蓝"]).zfill(2)])
    return rows


def fetch_latest():
    """联网抓取中彩网最近20期（实验性解析器，依赖页面结构；任何异常或校验不通过即由调用方回退）。"""
    url = "https://www.zhcw.com/kjxx/ssq/?t=50"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    periods = re.findall(r"20\d{6}", html)
    balls = re.findall(r">(\d{2})<", html)
    cand, idx = [], 0
    while idx + 7 <= len(balls):
        grp = balls[idx:idx + 7]
        if all(1 <= int(x) <= 33 for x in grp[:6]) and 1 <= int(grp[6]) <= 16:
            cand.append(grp); idx += 7
        else:
            idx += 1
    if len(cand) >= 20 and len(periods) >= 20:
        rows = []
        for p, g in zip(periods[:20], cand[:20]):
            rows.append([p, "", *g])  # 日期留空，由下游校验提示用户补全
        return rows
    raise RuntimeError(f"解析期数={len(periods)} 候选组={len(cand)}，不足以重组20期")


def resolve_rows():
    """按优先级解析数据源：--from-csv > --fetch > 本地CSV > 内置样本。"""
    args = sys.argv[1:]
    if "--from-csv" in args:
        p = args[args.index("--from-csv") + 1]
        print(f"[数据源] 本地CSV: {p}")
        return load_from_csv(p)
    if "--fetch" in args:
        try:
            print("[数据源] 尝试联网抓取中彩网最新20期...")
            rows = fetch_latest()
            passed, _ = validate(rows)
            if passed and len(rows) >= 20:
                print(f"[数据源] 抓取成功 {len(rows)} 期")
                return rows
            print("[警告] 抓取数据校验未通过，回退内置样本（建议改用 --from-csv 提供最新20期）")
        except Exception as e:
            print(f"[警告] 联网抓取失败({e})，回退内置样本。解析器可能需随中彩网页面更新；或改用 --from-csv。")
    local = os.path.join(OUT_DIR, "ssq_raw_20.csv")
    if os.path.exists(local):
        print(f"[数据源] 复用本地 {local}")
        return load_from_csv(local)
    print("[数据源] 使用内置样本(第2026062-2026081期)，离线可复现。")
    return [list(r) for r in RAW]


def main():
    rows = resolve_rows()
    passed, issues = validate(rows)
    csv_path = write_csv(rows)
    red_freq, blue_freq = build_frequency(rows)
    html_path = write_html(rows, red_freq, blue_freq, passed, issues)
    sum_path = write_summary(rows, red_freq, blue_freq, passed, issues)

    print("== 双色球数据库构建完成 ==")
    print(f"期数: {len(rows)}  (窗口 {rows[-1][0]} ~ {rows[0][0]})")
    print(f"CSV : {csv_path}")
    print(f"HTML: {html_path}")
    print(f"JSON: {sum_path}")
    print(f"校验: {'通过' if passed else '未通过'}")
    if issues:
        for i in issues:
            print("  -", i)
    print(f"红球最热: " + ", ".join(k for k, v in red_freq.items() if v == max(red_freq.values())))
    print(f"蓝球最热: " + ", ".join(k for k, v in blue_freq.items() if v == max(blue_freq.values())))


if __name__ == "__main__":
    main()
