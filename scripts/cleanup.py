# -*- coding: utf-8 -*-
"""清理误判 + 重建「命中清单」「统计」。

python3 cleanup.py --xlsx 表.xlsx --outdir 案例截图
"""
import argparse, collections, os, re, sys

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from media_map import media_of

PLATS = ["豆包", "DeepSeek", "千问", "元宝"]
HF = PatternFill("solid", fgColor="1F4E79")


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).replace("．", ".").replace("。", ".")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--sheet", default="Sheet1")
    ap.add_argument("--outdir", default="案例截图")
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.xlsx)
    ws = wb[args.sheet]
    head = [c.value for c in ws[1]]
    col = {h: i + 1 for i, h in enumerate(head)}
    for need in ["域名", "公司名称", "命中平台", "截图"]:
        if need not in col:
            sys.exit(f"缺少列「{need}」")

    dropped = []
    rows = []
    for r in range(2, ws.max_row + 1):
        dom_raw = ws.cell(row=r, column=col["域名"]).value
        if not dom_raw:
            continue
        dom = norm(dom_raw)
        domset = set(re.findall(r"[A-Za-z0-9\u4e00-\u9fa5-]+\.网址", dom if ".网址" in dom else dom + ".网址"))
        ok, bad, keep_shots = [], [], []
        for p in PLATS:
            if p not in col:
                continue
            v = ws.cell(row=r, column=col[p]).value
            if not v or not str(v).startswith("有"):
                continue
            hits = [h for h in re.split(r"[、,，]", str(v).split("：", 1)[-1]) if h]
            good = [h for h in hits if norm(h) in domset]
            if good:
                ok.append(p)
                ws.cell(row=r, column=col[p]).value = "有：" + "、".join(g.replace("。", ".") for g in good)
            else:
                bad.append((p, hits))
                ws.cell(row=r, column=col[p]).value = "× 非本行域名：" + "、".join(hits)
        shots = str(ws.cell(row=r, column=col["截图"]).value or "")
        for f in shots.split("；"):
            f = f.strip()
            if not f:
                continue
            if any(os.path.basename(f).startswith(p) for p in ok) and os.path.exists(f):
                keep_shots.append(f)
            elif os.path.exists(f) and f not in keep_shots:
                pass
        # 未命中的平台，其截图删除
        for f in shots.split("；"):
            f = f.strip()
            if f and f not in keep_shots and os.path.exists(f):
                os.remove(f)
        ws.cell(row=r, column=col["命中平台"]).value = "、".join(ok) or None
        ws.cell(row=r, column=col["截图"]).value = "；".join(keep_shots) or None
        if bad:
            note = "；".join(f"{p} 回答中的 {'、'.join(h)} 不是本行域名，已剔除" for p, h in bad)
            cur = ws.cell(row=r, column=col.get("备注", 1)).value if "备注" in col else None
            if "备注" in col:
                ws.cell(row=r, column=col["备注"]).value = (cur + "；" + note) if cur else note
            dropped.append((dom_raw, note))
        rows.append({
            "dom": dom_raw, "name": ws.cell(row=r, column=col["公司名称"]).value,
            "plats": ok, "shots": [os.path.basename(x) for x in keep_shots],
            "src": ws.cell(row=r, column=col["引用来源"]).value if "引用来源" in col else None,
        })

    # 删空目录
    if os.path.isdir(args.outdir):
        for d in os.listdir(args.outdir):
            p = os.path.join(args.outdir, d)
            if os.path.isdir(p) and not os.listdir(p):
                os.rmdir(p)

    hits = [x for x in rows if x["plats"]]
    for name in ("命中清单", "统计"):
        if name in wb.sheetnames:
            del wb[name]
    s = wb.create_sheet("命中清单", 1)
    s.append(["序号", "域名", "公司名称", "命中平台", "截图文件", "引用来源"])
    for c in s[1]:
        c.fill = HF
        c.font = Font(color="FFFFFF", bold=True, size=11)
        c.alignment = Alignment(horizontal="center", vertical="center")
    for i, x in enumerate(sorted(hits, key=lambda y: str(y["dom"])), 1):
        s.append([i, x["dom"], x["name"], "、".join(x["plats"]), "；".join(x["shots"]), x["src"]])
    for c, w in zip("ABCDEF", (6, 30, 34, 20, 50, 34)):
        s.column_dimensions[c].width = w
    s.freeze_panes = "A2"

    st = wb.create_sheet("统计", 2)
    tot = len(rows)
    c = collections.Counter()
    for x in hits:
        for p in x["plats"]:
            c[p] += 1
    for i, (k, v) in enumerate([
        ("企业总数", tot), ("至少一家 AI 提到 .网址", len(hits)),
        ("合并命中率", f"{len(hits) / tot:.1%}" if tot else "-"),
        ("豆包命中", c["豆包"]), ("DeepSeek命中", c["DeepSeek"]),
        ("千问命中", c["千问"]), ("元宝命中", c["元宝"]),
    ], 1):
        st.cell(row=i, column=1, value=k).font = Font(bold=(i <= 3))
        st.cell(row=i, column=2, value=v)
    st.column_dimensions["A"].width = 30
    st.column_dimensions["B"].width = 16

    wb.save(args.xlsx)
    print(f"命中 {len(hits)} 家 / 共 {tot} 家；剔除误判 {len(dropped)} 处")
    for d in dropped:
        print("  剔除:", d[0], "|", d[1])


if __name__ == "__main__":
    main()
