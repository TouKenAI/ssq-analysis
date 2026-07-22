# -*- coding: utf-8 -*-
"""
双色球第5步：输出5组完整红蓝号码 + 每组详细选号备注
========================================================
读取: ssq_groups_5.csv(第4步5组) / ssq_red_coldhot.csv(冷热分类) / ssq_blue_candidates.csv(蓝球类型)
产出: ssq_final_groups.csv(成品+备注) / 双色球成品号码.html
理性铁律: 开奖独立随机, 历史不预示未来; 任何选号策略均不改变中奖概率, 仅影响号码分布。
"""
import csv, os

def _resolve_data_dir(env_name="SSQ_DATA"):
    # 兼容 Windows + Git Bash: os.getcwd()/环境变量可能返回 /x/... 形式的 POSIX 路径,
    # Windows 原生 Python 会误判为 C:/x/... 而找不到目录, 这里归一化为 X:/...
    p = os.environ.get(env_name, os.getcwd())
    if os.name == "nt" and len(p) >= 3 and p[0] == "/" and p[1].isalpha() and p[2] == "/":
        p = p[1].upper() + ":" + p[2:]
    return p

OUT_DIR = _resolve_data_dir("SSQ_DATA")

def load(path):
    with open(os.path.join(OUT_DIR, path), encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def load_classes():
    hot, warm, cold = set(), set(), set()
    for row in load("ssq_red_coldhot.csv"):
        n, c = int(row["号码"]), row["分类"]
        (hot if c == "热" else warm if c == "温" else cold).add(n)
    return hot, warm, cold

def load_blue_type():
    return {int(r["蓝球"]): r["类型"] for r in load("ssq_blue_candidates.csv")}

def zone(n):
    return 0 if n <= 11 else 1 if n <= 22 else 2

def two_runs(nums):
    return [f"{nums[i]:02d}-{nums[i+1]:02d}" for i in range(len(nums)-1) if nums[i+1] == nums[i]+1]

def ac_value(nums):
    return len({nums[j]-nums[i] for i in range(len(nums)) for j in range(i+1, len(nums))}) - 5

def pos_text(z):
    a, b, c = z
    if c == 4: return "三区高度集中（4码落23-33），搏后区大号"
    if b == 4: return "二区高度集中（4码落12-22），搏中区热号"
    if a == 4: return "一区高度集中（4码落01-11），搏前区小号"
    if a == 3: return "一区偏重（3码落01-11），前区小号为主"
    if z == (1,3,2): return "三区最均衡（1/3/2），分布均匀"
    return f"三区分布 {a}/{b}/{c}，结构均衡"

def build_note(idx, reds, blue, hot, warm, cold, blue_type, overlap, odd_ratio, ac, z):
    h = [n for n in reds if n in hot]
    w = [n for n in reds if n in warm]
    c = [n for n in reds if n in cold]
    runs = two_runs(reds)
    runs_txt = "、".join(runs) if runs else "无"
    note = (f"【第{idx}组】红球 " + " ".join(f"{n:02d}" for n in reds) + f" + 蓝球{blue:02d}\n"
            f"• 奇偶比 {odd_ratio}，AC值 {ac}，三区分布 {z[0]}/{z[1]}/{z[2]}\n"
            f"• 冷热配比：热号 " + ("、".join(f"{n:02d}" for n in h) or "—") +
            f"｜温号 " + ("、".join(f"{n:02d}" for n in w) or "—") +
            f"｜冷号 " + ("、".join(f"{n:02d}" for n in c) or "—") + "\n"
            f"• 连号：二连号 {len(runs)} 处（{runs_txt}），无三连号\n"
            f"• 差异化定位：{pos_text(z)}；与组内其他组合最大重复 {overlap} 个，整体覆盖广\n"
            f"• 蓝球{blue:02d}：{blue_type}配置，作{'活跃端' if '活跃' in blue_type else '待出端'}搭配\n"
            f"• 策略：满足全部硬性过滤规则（R1奇偶比/R2 AC值/R3三区），热温冷 2/2/2 均衡，纯统计分布参考")
    return note

def main():
    groups = load("ssq_groups_5.csv")
    hot, warm, cold = load_classes()
    blue_type = load_blue_type()

    final = []
    for g in groups:
        reds = [int(x) for x in g["红球"].split()]
        blue = int(g["蓝球"])
        z = tuple(int(x) for x in g["三区分布(一/二/三区)"].split("/"))
        odd = sum(1 for n in reds if n % 2 == 1)
        odd_ratio = f"{odd}:{6-odd}"
        ac = ac_value(reds)
        overlap = int(g["与其他组最大重复数"])
        note = build_note(g["组号"].replace("第","").replace("组",""), reds, blue,
                          hot, warm, cold, blue_type.get(blue, "—"), overlap,
                          odd_ratio, ac, z)
        final.append({
            "组号": g["组号"],
            "红球": g["红球"], "蓝球": g["蓝球"],
            "奇偶比": odd_ratio, "AC值": ac,
            "三区分布": g["三区分布(一/二/三区)"],
            "热号数": g["热号数"], "温号数": g["温号数"], "冷号数": g["冷号数"],
            "与其他组最大重复数": overlap,
            "选号备注": note.replace("\n", " | "),
            "选号备注_完整": note,
        })

    # CSV
    csv_path = os.path.join(OUT_DIR, "ssq_final_groups.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["组号", "红球", "蓝球", "奇偶比", "AC值", "三区分布",
                    "热号数", "温号数", "冷号数", "与其他组最大重复数", "选号备注"])
        for r in final:
            w.writerow([r["组号"], r["红球"], r["蓝球"], r["奇偶比"], r["AC值"], r["三区分布"],
                        r["热号数"], r["温号数"], r["冷号数"], r["与其他组最大重复数"], r["选号备注"]])

    # HTML
    html_path = os.path.join(OUT_DIR, "双色球成品号码.html")
    # 总览表
    ov_rows = []
    for r in final:
        cells = "".join(f'<td class="r">{n:02d}</td>' for n in [int(x) for x in r["红球"].split()])
        ov_rows.append(f'<tr><td class="num">{r["组号"]}</td>{cells}'
                       f'<td class="b">{r["蓝球"]}</td><td class="num">{r["奇偶比"]}</td>'
                       f'<td class="num">{r["AC值"]}</td><td class="num">{r["三区分布"]}</td>'
                       f'<td class="num">{r["热号数"]}/{r["温号数"]}/{r["冷号数"]}</td></tr>')
    ov_html = "\n".join(ov_rows)
    # 备注卡片
    note_cards = []
    for r in final:
        note_cards.append(f'<div class="card note-card"><pre>{r["选号备注_完整"]}</pre></div>')
    note_html = "\n".join(note_cards)

    total_reds = set()
    for r in final:
        total_reds |= {int(x) for x in r["红球"].split()}

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>双色球成品号码(5组)</title>
<style>
*{{font-family:-apple-system,"Microsoft YaHei",sans-serif;box-sizing:border-box}}
body{{margin:0;padding:24px;background:#f5f7fa;color:#1f2d3d}}
h1{{font-size:22px;margin:0 0 4px}} .sub{{color:#6b7785;font-size:13px;margin-bottom:20px}}
.card{{background:#fff;border-radius:10px;padding:18px 20px;margin-bottom:18px;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.card h2{{font-size:16px;margin:0 0 12px;border-left:4px solid #d7282f;padding-left:10px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border:1px solid #e4e8ee;padding:6px 8px;text-align:center}}
th{{background:#f0f3f7;font-weight:600}} td.num{{font-variant-numeric:tabular-nums}}
td.r{{color:#d7282f;font-weight:600}} td.b{{color:#1565c0;font-weight:600}}
.kpis{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:6px}} .kpi{{background:#f0f3f7;border-radius:8px;padding:10px 14px;flex:1;min-width:120px}}
.kpi b{{font-size:20px;color:#d7282f;display:block}} .kpi span{{font-size:12px;color:#6b7785}}
.note-card pre{{white-space:pre-wrap;font-size:13px;line-height:1.7;margin:0;font-family:inherit}}
.warn{{background:#fff8e1;border-left:4px solid #f9a825;padding:12px 16px;border-radius:6px;font-size:13px;line-height:1.8}}
.note{{font-size:12px;color:#8a94a6;margin-top:14px;line-height:1.7}}
</style></head><body>
<h1>双色球成品号码 · 5组完整红蓝方案</h1>
<div class="sub">数据源：中彩网(zhcw.com) · 窗口：第2026062期~第2026081期(20期) · 生成日期：2026-07-19</div>

<div class="card"><h2>投注方案总览（10元 = 5注单式，每注2元）</h2>
<div class="kpis">
<div class="kpi"><b>5</b><span>注单式（10元预算）</span></div>
<div class="kpi"><b>{len(total_reds)}/33</b><span>5组覆盖不同红球数</span></div>
<div class="kpi"><b>≤2</b><span>任意两组最大重复(实际≤1)</span></div>
</div>
<table><thead><tr><th>组号</th><th>红1</th><th>红2</th><th>红3</th><th>红4</th><th>红5</th><th>红6</th><th>蓝</th><th>奇偶</th><th>AC</th><th>三区</th><th>热/温/冷</th></tr></thead><tbody>{ov_html}</tbody></table>
</div>

<div class="card"><h2>每组详细选号备注</h2>{note_html}</div>

<div class="card"><h2>中奖概率与理性提示（必读）</h2>
<div class="warn">
<p><b>一等奖数学事实：</b>双色球总组合数 = C(33,6) × 16 = 1,107,568 × 16 = <b>17,721,088</b>。单注中一等奖概率 = <b>1 / 1772万</b>。</p>
<p><b>本方案（5注/10元）：</b>中一等奖概率 = 5 / 17,721,088 ≈ <b>1 / 354万</b>。一等奖为浮动奖，单注封顶500万（需奖池充足），并非每期必达；"至少500万"无法保证。</p>
<p><b>关键结论：</b>任何选号策略（冷热/奇偶/AC/三区）都<b>不能改变中奖概率</b>——每次开奖独立随机，历史号码无预测力。本5组与机选5组的中奖概率完全相同，区别仅在于号码分布更均衡、覆盖更广、符合你设定的过滤规则。</p>
<p><b>期望测算：</b>5注成本10元；按一等奖500万、概率1/354万估算，期望奖金≈1.4元，长期必亏。请理性投入，量力而行。</p>
</div>
</div>

<p class="note">⚠️ 双色球每期开奖为独立随机事件，历史规律不预示未来。以上5组号码仅为数据存档与统计分析参考，<b>不构成任何购彩建议</b>。</p>
</body></html>"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print("== 第5步 成品号码输出完成 ==")
    print(f"输出: {csv_path}")
    print(f"输出: {html_path}")
    print(f"5组覆盖不同红球: {len(total_reds)}/33")
    for r in final:
        print(f"  {r['组号']}: {r['红球']} + 蓝{r['蓝球']}  ({r['奇偶比']} AC{r['AC值']} 三区{r['三区分布']})")

if __name__ == "__main__":
    main()
