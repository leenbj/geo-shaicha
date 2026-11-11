# -*- coding: utf-8 -*-
"""预处理：校验列、推导公司简称、抽样打印供人工确认。

python3 prepare.py --xlsx 表.xlsx --sheet Sheet1
"""
import argparse, re, sys

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

PROV = "北京|上海|天津|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|广西|海南|四川|贵州|云南|陕西|甘肃|青海|宁夏|新疆|内蒙古|西藏"
INDUSTRY = ["文化传播", "文化传媒", "网络科技", "信息科技", "智能科技", "新能源科技", "新能源", "餐饮管理", "酒店管理",
            "企业管理", "商业保理", "电子商务", "供应链管理", "供应链", "国际贸易", "贸易", "商贸", "实业", "科技",
            "食品", "建材", "装饰材料", "装饰工程", "装潢工程", "工程", "机械", "电子", "生物", "农业", "健康", "医药",
            "化妆品", "服饰", "服装", "家具", "包装", "设备", "材料", "检测", "数码影像", "信息技术", "能源", "环保",
            "物流", "咨询", "管理", "服务", "发展", "销售", "制造", "制品", "加工", "制衣", "皮鞋", "干果", "水产",
            "茶业", "种业", "矿产品", "铝业", "热系统", "船舶", "粉末", "焊接", "工具", "器材", "文体用品"]


def short_name(name: str) -> str:
    s = re.sub(r"[（(][^）)]*[）)]", "", name or "").strip()
    s = re.sub(r"(股份)?有限(责任)?公司$|集团$|公司$", "", s)
    s = re.sub(r"(厂|店|商行|商贸行|中心|合作社|经营部|服务部|工作室|事务所|批发部|门市部|餐厅|旅行社|批发总汇)$", "", s)
    s = s.replace("中国", "")
    s = re.sub(r"^(%s)(省|市|自治区)?" % PROV, "", s)
    for _ in range(2):
        s = re.sub(r"^[\u4e00-\u9fa5]{2,3}(市|区|县|旗)", "", s)
    for w in sorted(INDUSTRY, key=len, reverse=True):
        if s.endswith(w) and len(s) - len(w) >= 2:
            s = s[: -len(w)]
            break
    return s.strip("·-— ") or (name or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--sheet", default="Sheet1")
    ap.add_argument("--domain-col", default="域名")
    ap.add_argument("--name-col", default="公司名称")
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.xlsx)
    ws = wb[args.sheet]
    head = [c.value for c in ws[1]]
    for need in (args.domain_col, args.name_col):
        if need not in head:
            sys.exit(f"缺少列「{need}」，实际列：{head}")
    dc, nc = head.index(args.domain_col) + 1, head.index(args.name_col) + 1

    if "公司简称" not in head:
        c = ws.cell(row=1, column=len(head) + 1, value="公司简称")
        c.fill = PatternFill("solid", fgColor="1F4E79")
        c.font = Font(color="FFFFFF", bold=True, size=11)
        c.alignment = Alignment(horizontal="center", vertical="center")
        head.append("公司简称")
    sc = head.index("公司简称") + 1
    ws.column_dimensions[get_column_letter(sc)].width = 20

    seen, dup, blank = set(), [], 0
    n = 0
    for r in range(2, ws.max_row + 1):
        dom = ws.cell(row=r, column=dc).value
        name = ws.cell(row=r, column=nc).value
        if not dom and not name:
            continue
        if not name:
            blank += 1
            continue
        n += 1
        if dom in seen:
            dup.append(dom)
        seen.add(dom)
        if not (ws.cell(row=r, column=sc).value or "").strip():   # 已有简称不覆盖
            ws.cell(row=r, column=sc).value = short_name(str(name))
    wb.save(args.xlsx)

    print(f"有效行 {n}；重复域名 {len(dup)} {dup[:5]}；缺公司名 {blank}")
    print("抽样（重点看 2-3 字的人名、带括号的全称、一格多域名）：")
    shown = 0
    for r in range(2, ws.max_row + 1):
        if shown >= 15:
            break
        name = ws.cell(row=r, column=nc).value
        if not name:
            continue
        print(f"  {ws.cell(row=r, column=dc).value} | {name} -> {ws.cell(row=r, column=sc).value}")
        shown += 1


if __name__ == "__main__":
    main()
