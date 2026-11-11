// 腾讯元宝 worker（单平台）
// 入参 /tmp/aidv_yb_task.json: { company, short, domain, outDir, spaceId, label, renew, collectSources }
// 出参 stdout: { company, domain, results: [{platform:"元宝", answer1, answer2, hits, shot, sources, error}] }
const fs = await import("node:fs/promises");
const t0 = JSON.parse(await fs.readFile("/tmp/aidv_yb_task.json", "utf8"));
const task = await taskSpace(t0.spaceId);
const page = task.page(t0.label || "p1");
const URL = t0.url || "https://yuanbao.tencent.com/chat/naQivTmsDa";
const SEL = ".hyc-content-md";
const Q1 = `${t0.company}的官网是什么？`;
const Q2 = `${t0.short}的官网是什么？`;
const RE = /[A-Za-z0-9\u4e00-\u9fa5\u00b7-]{2,}[.．。·・]网址/g;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function typeAsk(q) {
  const ce = await page.evaluate(() => document.querySelectorAll('[contenteditable="true"]').length);
  if (ce > 0) {
    await page.click('[contenteditable="true"]');
    await page.keyboard.insertText(q);
    await page.waitForTimeout(400);
    await page.keyboard.press("Enter");
  } else {
    await page.fill("textarea", q);
    await page.press("textarea", "Enter");
  }
}

async function readAnswer(strip) {
  await page.waitForTimeout(8000);
  let prev = "", stable = 0;
  for (let i = 0; i < 40; i++) {
    const t = await page.evaluate((s) => {
      const n = document.querySelectorAll(s);
      return n.length ? n[n.length - 1].innerText : "";
    }, SEL);
    if (t && t === prev) {
      stable++;
      if (stable >= 2) break;
    } else stable = 0;
    prev = t;
    await page.waitForTimeout(2000);
  }
  let ans = (prev || "").trim();
  if (strip && ans.includes(strip)) ans = ans.slice(ans.indexOf(strip) + strip.length).trim();
  return ans;
}

async function shot(name, question) {
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
    }, { s: SEL, qq: question });
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

// 元宝：点左下角「数据引用源」或回答里的引用图标，抓来源
async function collectSources() {
  const out = [];
  const push = (title, url) => {
    if (url && !/yuanbao\.tencent\.com/.test(url) && !out.some((s) => s.url === url)) {
      out.push({ title: (title || "").slice(0, 80), url });
    }
  };
  try {
    const trig = await page.evaluate(() => {
      const els = [...document.querySelectorAll("div,span,button,a")].filter((e) => {
        const t = (e.innerText || "").trim();
        return /数据引用源|引用源|参考.*篇|篇资料/.test(t) && t.length < 20;
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
      const items = await page.evaluate(() =>
        [...document.querySelectorAll("a")].map((a) => ({ t: (a.innerText || "").trim().slice(0, 80), u: a.href }))
      );
      items.forEach((i) => push(i.t, i.u));
    }
    if (!out.length) {
      const total = await page.evaluate(() => {
        const ans = [...document.querySelectorAll(SEL)].pop();
        return ans ? ans.querySelectorAll('[class*="ref-list__item"]').length : 0;
      });
      for (let i = 0; i < Math.min(total, 8); i++) {
        const pt = await page.evaluate((idx) => {
          const ans = [...document.querySelectorAll(".hyc-content-md")].pop();
          if (!ans) return null;
          const items = [...ans.querySelectorAll('[class*="ref-list__item"]')];
          const el = items[idx];
          if (!el) return null;
          el.scrollIntoView({ block: "center" });
          const b = el.getBoundingClientRect();
          return { x: Math.round(b.x + b.width / 2), y: Math.round(b.y + b.height / 2) };
        }, i);
        if (!pt) continue;
        await page.mouse.click(pt.x, pt.y);
        await page.waitForTimeout(1600);
        const tabs = await task.tabs();
        const ext = tabs.filter((t) => t.url && !t.url.includes("yuanbao.tencent.com"));
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

const rec = { platform: "元宝", answer1: "", answer2: "", hits: [], shot: "", sources: [], error: "" };
try {
  const needNav = await page.evaluate(
    () => !/yuanbao\.tencent\.com/.test(location.href) || document.querySelectorAll('[contenteditable="true"]').length === 0
  );
  if (needNav || t0.renew) {
    await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(3500);
    if (t0.renew) {
      try {
        await page.click("text=新建对话", { timeout: 4000 });
        await page.waitForTimeout(2000);
      } catch (e) {}
    }
  }
  await typeAsk(Q1);
  rec.answer1 = await readAnswer(Q1);
  let hits = rec.answer1.match(RE) || [];
  if (!hits.length) {
    await sleep(3500 + Math.floor(Math.random() * 2500));
    await typeAsk(Q2);
    rec.answer2 = await readAnswer(Q2);
    hits = rec.answer2.match(RE) || [];
    if (hits.length) rec.shot = await shot("元宝-简称", Q2);
  } else {
    rec.shot = await shot("元宝-全称", Q1);
  }
  const norm = (x) => String(x || "").replace(/\s+/g, "").replace(/[。．··]/g, ".");
  const want = (() => { const d = norm(t0.domain); return d.includes(".网址") ? d : d + ".网址"; })();
  rec.hits = [...new Set(hits.map((h) => h.replace(/[。·・]/g, ".")))]
    .filter((h) => norm(h) === want);
  if (rec.hits.length && t0.collectSources) rec.sources = await collectSources();
} catch (e) {
  rec.error = String(e).slice(0, 300);
}
console.log(JSON.stringify({ company: t0.company, domain: t0.domain, results: [rec] }));
