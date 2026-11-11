# -*- coding: utf-8 -*-
"""主驱动：按表格顺序在 豆包/DeepSeek/千问/元宝 提问，判定 .网址，命中截图，回写表格。

用法：
  python3 run.py --xlsx 表.xlsx --space 12 --platforms doubao,deepseek,qianwen
  python3 run.py --xlsx 表.xlsx --space 13 --platforms yuanbao
  python3 run.py --xlsx 表.xlsx --space 12 --citations-only      # 只补引用来源
  python3 run.py --xlsx 表.xlsx --space 12 --limit 10 --reset     # 重跑前 10 行
"""
import argparse, json, os, random, re, subprocess, sys, time

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from media_map import media_of

HERE = os.path.dirname(os.path.abspath(__file__))
CHAT_KEYS = ["豆包", "DeepSeek", "千问"]
ALL_KEYS = CHAT_KEYS + ["元宝"]
ALIAS = {"doubao": "豆包", "deepseek": "DeepSeek", "qianwen": "千问", "yuanbao": "元宝"}

HF = PatternFill("solid", fgColor="1F4E79")
HFONT = Font(color="FFFFFF", bold=True, size=11)


def ensure_cols(ws):
    head = [c.value for c in ws[1]]
    want = ALL_KEYS + ["命中平台", "截图", "状态", "引用来源", "引用链接"]
    for name in want:
        if name not in head:
            c = ws.cell(row=1, column=len(head) + 1, value=name)
            c.fill = HF
            c.font = HFONT
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            head.append(name)
    widths = {"豆包": 20, "DeepSeek": 20, "千问": 20, "元宝": 20, "命中平台": 14,
              "截图": 40, "状态": 10, "引用来源": 34, "引用链接": 46}
    for name, w in widths.items():
        ws.column_dimensions[get_column_letter(head.index(name) + 1)].width = w
    ws.row_dimensions[1].height = 32
    ws.auto_filter.ref = f"A1:{get_column_letter(len(head))}{ws.max_row}"
    return {h: i + 1 for i, h in enumerate(head)}


def run_worker(worker, payload, tmp):
    json.dump(payload, open(tmp, "w"), ensure_ascii=False)
    p = subprocess.run(["ego-browser", "nodejs"], stdin=open(worker), capture_output=True, text=True, timeout=1200)
    raw = (p.stdout or "").strip() or (p.stderr or "").strip()
    i = raw.find('{"company"')
    if i < 0:
        i = raw.find("{")
    if i < 0:
        raise RuntimeError((p.stderr or raw)[-300:])
    return json.loads(raw[i:])


def write_cell(ws, col, r, name, value):
    c = ws.cell(row=r, column=col[name], value=value)
    c.alignment = Alignment(vertical="top", wrap_text=True)
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--sheet", default="Sheet1")
    ap.add_argument("--space", type=int, required=True)
    ap.add_argument("--outdir", default="案例截图")
    ap.add_argument("--platforms", default="doubao,deepseek,qianwen,yuanbao")
    ap.add_argument("--limit", type=int, default=10000)
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--citations-only", action="store_true")
    ap.add_argument("--no-sources", action="store_true")
    ap.add_argument("--renew-every", type=int, default=10)
    args = ap.parse_args()

    plats = [ALIAS.get(x.strip(), x.strip()) for x in args.platforms.split(",") if x.strip()]
    bad = [p for p in plats if p not in ALL_KEYS]
    if bad:
        sys.exit(f"未知平台: {bad}，可选 {ALL_KEYS}")

    outdir = os.path.abspath(args.outdir)
    wb = openpyxl.load_workbook(args.xlsx)
    ws = wb[args.sheet]
    col = ensure_cols(ws)

    targets = []
    for r in range(2, ws.max_row + 1):
        dom = ws.cell(row=r, column=col["域名"]).value if "域名" in col else None
        if not dom:
            continue
        if args.citations_only:
            if ws.cell(row=r, column=col["命中平台"]).value:
                targets.append(r)
            continue
        if args.reset:
            for n in plats + ["命中平台", "截图", "状态", "引用来源", "引用链接"]:
                ws.cell(row=r, column=col[n]).value = None
        if ws.cell(row=r, column=col["状态"]).value == "已完成":
            continue
        targets.append(r)
    targets = targets[: args.limit]
    wb.save(args.xlsx)
    print(f"待处理 {len(targets)} 行；平台 {plats}", flush=True)

    use_chat = any(p in CHAT_KEYS for p in plats)
    tmp_chat = "/tmp/aidv_task.json"
    tmp_yb = "/tmp/aidv_yb_task.json"

    for n, r in enumerate(targets, 1):
        dom = ws.cell(row=r, column=col["域名"]).value
        comp = ws.cell(row=r, column=col["公司名称"]).value
        short = (ws.cell(row=r, column=col["公司简称"]).value if "公司简称" in col else None) or comp
        print(f"[{n}/{len(targets)}] {dom} / {comp} / {short}", flush=True)
        renew = (n - 1) % max(1, args.renew_every) == 0
        hit_plats, shots, src_pairs, src_urls = [], [], [], []

        def absorb(data):
            for res in data.get("results", []):
                plat = res.get("platform")
                if plat not in plats:
                    continue
                cell = ws.cell(row=r, column=col[plat])
                if res.get("error"):
                    write_cell(ws, col, r, plat, "失败")
                    continue
                if res.get("hits"):
                    write_cell(ws, col, r, plat, "有：" + "、".join(res["hits"]))
                    hit_plats.append(plat)
                    if res.get("shot"):
                        shots.append(res["shot"])
                    for s in res.get("sources") or []:
                        m = media_of(s.get("url"))
                        if m:
                            src_pairs.append(f"{plat}:{m}")
                            src_urls.append(s.get("url"))
                else:
                    write_cell(ws, col, r, plat, "无")

        try:
            if use_chat:
                data = run_worker(os.path.join(HERE, "worker_chat.js"), {
                    "company": comp, "short": short, "domain": dom, "outDir": outdir,
                    "spaceId": args.space, "renew": renew, "only": [p for p in plats if p in CHAT_KEYS],
                    "collectSources": (not args.no_sources) and (not args.citations_only),
                }, tmp_chat)
                absorb(data)
                if args.citations_only:
                    pass
            if "元宝" in plats:
                data = run_worker(os.path.join(HERE, "worker_yuanbao.js"), {
                    "company": comp, "short": short, "domain": dom, "outDir": outdir,
                    "spaceId": args.space, "label": "p4", "renew": renew,
                    "collectSources": (not args.no_sources) and (not args.citations_only),
                }, tmp_yb)
                absorb(data)

            write_cell(ws, col, r, "命中平台", "、".join(dict.fromkeys(hit_plats)) or None)
            write_cell(ws, col, r, "截图", "；".join(dict.fromkeys(shots)) or None)
            if src_pairs:
                write_cell(ws, col, r, "引用来源", "；".join(dict.fromkeys(src_pairs)))
                write_cell(ws, col, r, "引用链接", "；".join(list(dict.fromkeys(src_urls))[:6]))
            write_cell(ws, col, r, "状态", "已完成")
            wb.save(args.xlsx)
            print(f"    -> 命中 {hit_plats or '无'} 截图{len(shots)}张 来源{len(set(src_pairs))}种", flush=True)
        except Exception as e:
            write_cell(ws, col, r, "状态", "失败")
            wb.save(args.xlsx)
            print(f"    !! {str(e)[:200]}", flush=True)
        if n < len(targets):
            time.sleep(15 + random.randint(0, 15))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
