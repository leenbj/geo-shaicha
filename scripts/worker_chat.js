// 豆包 / DeepSeek / 千问 三平台 worker
// 入参 /tmp/aidv_task.json: { company, short, domain, outDir, spaceId, labels, renew, collectSources }
// 出参 stdout: { company, domain, results: [{platform, answer1, answer2, hits, shot, sources, error}] }
const fs = await import("node:fs/promises");
const t0 = JSON.parse(await fs.readFile("/tmp/aidv_task.json", "utf8"));
const task = await taskSpace(t0.spaceId);
const L = t0.labels || {};

const Q1 = `${t0.company}的官网是什么？`;
const Q2 = `${t0.short}的官网是什么？`;
const RE = /[A-Za-z0-9\u4e00-\u9fa5\u00b7-]{2,}[.．。·・]网址/g;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const PLATFORMS = [
  {
    key: "豆包",
    label: L.doubao || "p1",
    url: "https://www.doubao.com/chat/",
    newChat: "text=新对话",
    sel: '[class*="md-box-root"]',
  },
  {
    key: "DeepSeek",
    label: L.deepseek || "p2",
    url: "https://chat.deepseek.com/",
    newChat: "text=开启新对话",
    sel: ".ds-markdown",
  },
  {
    key: "千问",
    label: L.qianwen || "p3",
    url: "https://www.qianwen.com/",
    newChat: "text=新对话",
    sel: ".qk-markdown",
  },
];

async function typeAsk(page, q) {
  const st = await page.evaluate(() => ({
    ta: document.querySelectorAll("textarea").length,
    ce: document.querySelectorAll('[contenteditable="true"]').length,
  }));
  if (st.ta > 0) {
    await page.fill("textarea", q);
    await page.press("textarea", "Enter");
  } else if (st.ce > 0) {
    await page.click('[contenteditable="true"]');
    await page.keyboard.insertText(q);
    await page.waitForTimeout(400);
    await page.keyboard.press("Enter");
  } else {
    throw new Error("输入框未找到 " + JSON.stringify(st));
  }
}

async function readAnswer(page, sel, strip) {
  await page.waitForTimeout(7000);
  let prev = "", stable = 0;
  for (let i = 0; i < 40; i++) {
    const t = await page.evaluate((s) => {
      const n = document.querySelectorAll(s);
      return n.length ? n[n.length - 1].innerText : "";
    }, sel);
    if (t && t === prev) {
      stable++;
      if (stable >= 2) break;
    } else stable = 0;
    prev = t;
    await page.waitForTimeout(2000);
  }
  let ans = (prev || "").trim();
  if (strip && ans.includes(strip)) ans = ans.slice(ans.indexOf(strip) + strip.length).trim();
  return ans.replace(/^AI 生成可能有误[^\n]*\n?/, "").trim();
}

// 只截「本次提问 + 本次回答」：克隆进白色浮层再截，避免同会话其他企业内容入镜
async function shot(page, name, sel, question) {
  const dir = `${t0.outDir}/${t0.domain}`;
  await fs.mkdir(dir, { recursive: true });
  const file = `${dir}/${name}.png`;
  try {
    const ok = await page.evaluate(({ s, qq }) => {
      const list = document.querySelectorAll(s);
      const aEl = list[list.length - 1];
      if (!aEl) return false;
      const norm = (t) => (t || "").replace(/\s+/g, " ").trim();
      const qEl = [...document.querySelectorAll("div,span,p")]
        .filter((e) => norm(e.innerText) === norm(qq))
        .sort((a, b) => a.getBoundingClientRect().height - b.getBoundingClientRect().height)[0];
      const box = document.createElement("div");
      box.id = "__ego_shot";
      box.style.cssText =
        "position:fixed;inset:0;background:#fff;z-index:2147483647;padding:22px;overflow:hidden;box-sizing:border-box";
      const inner = document.createElement("div");
      inner.style.cssText = "width:900px;transform-origin:top left";
      if (qEl) {
        const qc = qEl.cloneNode(true);
        if (!(qc.innerText || "").trim()) qc.textContent = qq;   // 千问气泡克隆后为空，用已知问句补上
        qc.style.cssText +=
          ";display:inline-block;background:#f2f3f5;border-radius:10px;padding:8px 12px;margin:0 0 10px auto;float:right;clear:both;max-width:70%;";
        inner.appendChild(qc);
      }
      const clear = document.createElement("div");
      clear.style.clear = "both";
      inner.appendChild(clear);
      const ac = aEl.cloneNode(true);
      ac.style.cssText += ";display:block;margin-top:8px;";
      inner.appendChild(ac);
      box.appendChild(inner);
      document.documentElement.appendChild(box);
      const h = inner.scrollHeight, vh = window.innerHeight;
      inner.style.transform = `scale(${Math.min(1, (vh - 30) / h)})`;
      return true;
    }, { s: sel, qq: question });
    await page.waitForTimeout(400);
    await page.screenshot({ path: file });
    await page.evaluate(() => document.getElementById("__ego_shot")?.remove());
    if (!ok) throw new Error("overlay failed");
  } catch (e) {
    try {
      await page.evaluate(() => document.getElementById("__ego_shot")?.remove());
    } catch (e2) {}
    try {
      await page.screenshot({ path: file });
    } catch (e2) {}
  }
  return file;
}

// 采集引用来源：优先点「N 篇资料 / 数据引用源」，退化到直接点回答里的引用图标
async function collectSources(page, sel) {
  const out = [];
  const push = (title, url) => {
    if (url && !/doubao\.com|deepseek\.com|qianwen\.com|yuanbao\.tencent\.com/.test(url) && !out.some((s) => s.url === url)) {
      out.push({ title: (title || "").slice(0, 80), url });
    }
  };
  try {
    const trig = await page.evaluate(() => {
      const els = [...document.querySelectorAll("div,span,button,a")].filter((e) => {
        const t = (e.innerText || "").trim();
        return /^参考\s*\d+\s*篇资料$|^\d+\s*篇资料$|^数据引用源$|^来源$/.test(t);
      });
      if (!els.length) return null;
      const el = els[els.length - 1];
      el.scrollIntoView({ block: "center" });
      const b = el.getBoundingClientRect();
      return { x: Math.round(b.x + b.width / 2), y: Math.round(b.y + b.height / 2) };
    });
    if (trig) {
      await page.mouse.click(trig.x, trig.y);
      await page.waitForTimeout(2000);
      const panel = await page.evaluate(() =>
        [...document.querySelectorAll("a")].map((a) => ({ t: (a.innerText || "").trim().slice(0, 80), u: a.href }))
      );
      panel.forEach((p) => push(p.t, p.u));
      await page.keyboard.press("Escape").catch(() => {});
    }
    if (!out.length) {
      const total = await page.evaluate((s) => {
        const ans = [...document.querySelectorAll(s)].pop();
        return ans ? ans.querySelectorAll('[class*="ref-list__item"], a[href*="http"]').length : 0;
      }, sel);
      for (let i = 0; i < Math.min(total, 6); i++) {
        const pt = await page.evaluate(({ s, idx }) => {
          const ans = [...document.querySelectorAll(s)].pop();
          if (!ans) return null;
          const items = [...ans.querySelectorAll('[class*="ref-list__item"], a[href*="http"]')];
          const el = items[idx];
          if (!el) return null;
          el.scrollIntoView({ block: "center" });
          const b = el.getBoundingClientRect();
          return { x: Math.round(b.x + b.width / 2), y: Math.round(b.y + b.height / 2) };
        }, { s: sel, idx: i });
        if (!pt) continue;
        await page.mouse.click(pt.x, pt.y);
        await page.waitForTimeout(1600);
        const tabs = await task.tabs();
        const ext = tabs.filter((t) => t.url && !/doubao\.com|deepseek\.com|qianwen\.com|yuanbao\.tencent\.com/.test(t.url));
        ext.forEach((t) => push(t.title, t.url));
        for (const t of ext) {
          try {
            await t.page.close();
          } catch (e) {}
        }
      }
    }
  } catch (e) {}
  return out.slice(0, 8);
}

const only = Array.isArray(t0.only) && t0.only.length ? t0.only : null;
const list = only ? PLATFORMS.filter((p) => only.includes(p.key)) : PLATFORMS;
const results = [];
for (let i = 0; i < list.length; i++) {
  const cfg = list[i];
  const rec = { platform: cfg.key, answer1: "", answer2: "", hits: [], shot: "", sources: [], error: "" };
  try {
    if (i > 0) await sleep(15000 + Math.floor(Math.random() * 20000));
    const page = task.page(cfg.label);
    if (t0.renew) {
      await page.goto(cfg.url, { waitUntil: "domcontentloaded", timeout: 60000 });
      await page.waitForTimeout(3000);
      try {
        await page.click(cfg.newChat, { timeout: 5000 });
        await page.waitForTimeout(2500);
      } catch (e) {}
    } else {
      const ready = await page.evaluate(() => document.querySelectorAll("textarea,[contenteditable='true']").length > 0);
      if (!ready) {
        await page.goto(cfg.url, { waitUntil: "domcontentloaded", timeout: 60000 });
        await page.waitForTimeout(3000);
      }
    }
    await typeAsk(page, Q1);
    rec.answer1 = await readAnswer(page, cfg.sel, Q1);
    let hits = rec.answer1.match(RE) || [];
    if (!hits.length) {
      await sleep(4000 + Math.floor(Math.random() * 4000));
      await typeAsk(page, Q2);
      rec.answer2 = await readAnswer(page, cfg.sel, Q2);
      hits = rec.answer2.match(RE) || [];
      if (hits.length) {
        rec.shot = await shot(page, cfg.key + "-简称", cfg.sel, Q2);
      }
    } else {
      rec.shot = await shot(page, cfg.key + "-全称", cfg.sel, Q1);
    }
    const norm = (x) => String(x || "").replace(/\s+/g, "").replace(/[。．·・]/g, ".");
    const want = norm(t0.domain).includes(".网址") ? norm(t0.domain) : norm(t0.domain) + ".网址";
    rec.hits = [...new Set(hits.map((h) => h.replace(/[。·・]/g, ".")))]
      .filter((h) => norm(h) === want);   // 只用等值，避免子串误判
    if (rec.hits.length && t0.collectSources) rec.sources = await collectSources(page, cfg.sel);
  } catch (e) {
    rec.error = String(e).slice(0, 300);
  }
  results.push(rec);
}
console.log(JSON.stringify({ company: t0.company, domain: t0.domain, results }));
