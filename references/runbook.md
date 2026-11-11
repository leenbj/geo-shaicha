# AI 中文域名可见度检测 · 操作手册

配套 `SKILL.md` 使用。这份是“照着敲命令”的版本。

## 0. 前置

- ego lite 已装：`ego-browser --version`
- 豆包 / DeepSeek / 千问 / 元宝 **四个账号都已登录**（在 ego lite 里手工登一次，脚本不处理登录）
- 表格至少两列：`域名`、`公司名称`

## 1. 预处理

```bash
cd ~/.agents/skills/geo-shaicha

python3 scripts/prepare.py --xlsx /path/表.xlsx --sheet Sheet1
```

看输出抽样，重点三类异常：

| 异常 | 例子 | 处理 |
|---|---|---|
| 2–3 字的人名 | `吴涛`、`石同英` | 简称会等于人名，第二问可能问偏；可手工改成品牌名 |
| 带括号全称 | `迈凯伦（北京）酒店管理有限公司` | 正常，简称已剥括号 |
| 一格多域名 | `中国eleviva.网址   eleviva保健食品.网址` | 判定按集合匹配，能过 |

## 2. 开浏览器空间

```bash
ego-browser nodejs <<'EOF'
const t = await taskSpace("aidv");
const p1 = t.page("p1"); await p1.goto("https://www.doubao.com/chat/");
const p2 = await t.newPage(); await p2.goto("https://chat.deepseek.com/");
const p3 = await t.newPage(); await p3.goto("https://www.qianwen.com/");
const p4 = await t.newPage(); await p4.goto("https://yuanbao.tencent.com/chat/naQivTmsDa");
console.log(JSON.stringify({ spaceId: t.spaceId }));
EOF
```

记下 `spaceId`。元宝要在 `p4`。

## 3. 跑检测

```bash
python3 scripts/run.py --xlsx /path/表.xlsx --space 12 --outdir 案例截图 \
    --platforms doubao,deepseek,qianwen,yuanbao
```

只想跑某几个平台就改 `--platforms`。中断后重跑同一条命令会从断点继续（已完成行自动跳过）。

想重头跑：加 `--reset`（会清空这些平台的结果列）。

## 4. 补引用来源

```bash
python3 scripts/run.py --xlsx /path/表.xlsx --space 12 --citations-only
```

只对已命中的行重新提问，展开「数据引用源」，把来源 URL 写进 `引用链接`，媒体名写进 `引用来源`（如 `豆包:百家号；元宝:企查查`）。

失败很常见（登录墙、弹层点不到），属于 best-effort，不影响主流程。

## 5. 清理 + 出表

```bash
python3 scripts/cleanup.py --xlsx /path/表.xlsx --outdir 案例截图
```

- 命中值与域名做等值校验，答成别家的降级并删图
- 重建 `命中清单`、`统计`

## 6. 交付话术（三句话）

1. 总量：`N 家里 M 家被提到，合并命中率 X%`
2. 平台差异：`哪家 AI 最能捞（通常是豆包）；元宝能捞回其他三家都漏的 K 家`
3. 变量：`决定命中与否的是渠道覆盖数，不是单个平台`（1 平台 0% / 2 平台 23% / 3 平台 57%）

## 常见报错

| 报错 | 原因 | 处理 |
|---|---|---|
| `page label not found: p4` | 空间里没有这个标签页 | 先按第 2 步建页，或改 `--platforms` 只跑已有平台 |
| `输入框未找到` | 站点改版 / 未登录 | 手工打开该站看是否需要登录，再探选择器 |
| `hard stop`：用户已接管 | 用户点了浏览器 | 停手，等用户说“继续”，再 `claimTaskSpace(spaceId)` |
| 结果全是“无” | 提问发出去但没等到回答 | 看截图/页面，多半是回答容器选择器过期 |
