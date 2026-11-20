#!/usr/bin/env node
/**
 * AURA Live Browser — Persistent Playwright Chromium JSON-RPC Worker
 * Drives real multi-tab Chromium automation (navigate, click, type, press, scroll,
 * back, forward, reload, screenshot, DOM element inspection) over line-delimited
 * stdin/stdout JSON-RPC with strict SSRF defense-in-depth.
 */

import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import { pathToFileURL } from 'node:url';

const VIEWPORT = { width: 1280, height: 760 };

function findPlaywrightModule() {
  const candidates = [
    process.env.PLAYWRIGHT_CORE_PATH,
    'C:/Users/hp/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.js',
    path.join(process.env.USERPROFILE || '', '.cache', 'codex-runtimes', 'codex-primary-runtime', 'dependencies', 'node', 'node_modules', 'playwright-core', 'index.js'),
  ].filter(Boolean);
  for (const p of candidates) {
    try {
      if (fs.existsSync(p)) return p;
    } catch (_) {}
  }
  return null;
}

function findChromiumExecutable() {
  const explicit = process.env.AURA_CHROME_PATH;
  if (explicit && fs.existsSync(explicit)) return explicit;

  const localApp = process.env.LOCALAPPDATA || '';
  if (localApp) {
    const msPw = path.join(localApp, 'ms-playwright');
    if (fs.existsSync(msPw)) {
      try {
        const dirs = fs.readdirSync(msPw).filter((d) => d.startsWith('chromium-')).sort().reverse();
        for (const d of dirs) {
          const exeWin = path.join(msPw, d, 'chrome-win64', 'chrome.exe');
          const exeWin32 = path.join(msPw, d, 'chrome-win', 'chrome.exe');
          if (fs.existsSync(exeWin)) return exeWin;
          if (fs.existsSync(exeWin32)) return exeWin32;
        }
      } catch (_) {}
    }
  }

  const systemCandidates = [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/usr/bin/google-chrome',
  ];
  for (const c of systemCandidates) {
    try {
      if (fs.existsSync(c)) return c;
    } catch (_) {}
  }
  return undefined;
}

function isUrlAllowedByWorker(rawUrl) {
  try {
    const u = new URL(String(rawUrl || ''));
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return false;
    const h = (u.hostname || '').toLowerCase();
    if (!h) return false;
    if (
      h === 'localhost' ||
      h === '127.0.0.1' ||
      h === '::1' ||
      h === '[::1]' ||
      h === '0.0.0.0' ||
      h === '169.254.169.254' ||
      h.endsWith('.local') ||
      h.endsWith('.internal') ||
      h.endsWith('.localhost') ||
      /^10\./.test(h) ||
      /^192\.168\./.test(h) ||
      /^172\.(1[6-9]|2\d|3[0-1])\./.test(h) ||
      /^169\.254\./.test(h)
    ) {
      return false;
    }
    return true;
  } catch (_) {
    return false;
  }
}

let chromiumApi = null;
let browser = null;
let context = null;
const tabs = new Map();

async function ensureBrowser() {
  if (browser && browser.isConnected()) return;
  if (!chromiumApi) {
    let mod = null;
    try {
      mod = await import('playwright-core');
    } catch (_) {
      try {
        mod = await import('playwright');
      } catch (_2) {
        const foundPath = findPlaywrightModule();
        if (!foundPath) {
          throw new Error('playwright-core module not found');
        }
        mod = await import(pathToFileURL(foundPath).href);
      }
    }
    chromiumApi = mod.chromium || (mod.default && mod.default.chromium);
    if (!chromiumApi) throw new Error('playwright chromium export missing');
  }

  const executablePath = findChromiumExecutable();
  browser = await chromiumApi.launch({
    headless: true,
    executablePath,
    args: [
      '--disable-gpu',
      '--no-sandbox',
      '--disable-dev-shm-usage',
      '--disable-blink-features=AutomationControlled',
    ],
  });
  context = await browser.newContext({
    viewport: VIEWPORT,
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    ignoreHTTPSErrors: false,
  });
  await context.route('**/*', async (route) => {
    const reqUrl = route.request().url();
    if (reqUrl.startsWith('data:') || reqUrl.startsWith('blob:') || reqUrl === 'about:blank') {
      return route.continue();
    }
    if (!isUrlAllowedByWorker(reqUrl)) {
      return route.abort('blockedbyclient');
    }
    return route.continue();
  });
}

async function getOrCreateTab(tabId) {
  await ensureBrowser();
  const id = String(tabId || 'tab_1');
  let page = tabs.get(id);
  if (!page || page.isClosed()) {
    page = await context.newPage();
    page.setDefaultTimeout(15000);
    page.setDefaultNavigationTimeout(20000);
    tabs.set(id, page);
  }
  return { id, page };
}

async function captureTabSnapshot(page, includeElements = true) {
  const buf = await page.screenshot({ type: 'jpeg', quality: 68, fullPage: false });
  const screenshot_b64 = buf.toString('base64');
  const title = await page.title().catch(() => '');
  const url = page.url() || 'about:blank';

  let inspect = {
    text: '',
    scroll: { x: 0, y: 0, max_y: 0 },
    elements: [],
  };

  if (includeElements) {
    inspect = await page
      .evaluate(() => {
        const scrollY = Math.round(window.scrollY || 0);
        const scrollX = Math.round(window.scrollX || 0);
        const maxY = Math.max(0, Math.round((document.documentElement.scrollHeight || 0) - window.innerHeight));
        const bodyText = ((document.body && document.body.innerText) || '')
          .replace(/\s+/g, ' ')
          .trim()
          .slice(0, 5000);

        const nodes = document.querySelectorAll(
          'a[href], button, input:not([type="hidden"]), textarea, select, [role="button"], [role="link"]'
        );
        const items = [];
        for (const el of nodes) {
          if (items.length >= 36) break;
          const rect = el.getBoundingClientRect();
          if (rect.width < 8 || rect.height < 8) continue;
          if (rect.bottom < 0 || rect.top > window.innerHeight) continue;
          if (rect.right < 0 || rect.left > window.innerWidth) continue;
          const style = window.getComputedStyle(el);
          if (style.visibility === 'hidden' || style.display === 'none' || Number(style.opacity) === 0) continue;
          const tag = (el.tagName || '').toLowerCase();
          const label = (
            el.innerText ||
            el.getAttribute('aria-label') ||
            el.getAttribute('placeholder') ||
            el.getAttribute('title') ||
            el.getAttribute('name') ||
            el.getAttribute('value') ||
            ''
          )
            .replace(/\s+/g, ' ')
            .trim()
            .slice(0, 90);
          if (!label && tag !== 'input' && tag !== 'textarea') continue;
          items.push({
            index: items.length + 1,
            tag,
            type: el.getAttribute('type') || '',
            text: label || `${tag} field`,
            href: tag === 'a' ? (el.href || '').slice(0, 260) : '',
            x: Math.round(rect.left + rect.width / 2),
            y: Math.round(rect.top + rect.height / 2),
            w: Math.round(rect.width),
            h: Math.round(rect.height),
          });
        }
        return {
          text: bodyText,
          scroll: { x: scrollX, y: scrollY, max_y: maxY },
          elements: items,
        };
      })
      .catch(() => inspect);
  }

  return {
    url,
    title: title || url,
    viewport: VIEWPORT,
    screenshot_b64,
    scroll: inspect.scroll,
    page_text: inspect.text,
    elements: inspect.elements,
    engine: 'playwright_chromium',
  };
}

async function handleCommand(req) {
  const cmd = req.cmd;
  const tabId = req.tab_id || 'tab_1';

  if (cmd === 'ping') {
    await ensureBrowser();
    return { ok: true, engine: 'playwright_chromium', viewport: VIEWPORT, tab_count: tabs.size };
  }

  if (cmd === 'shutdown') {
    if (browser) await browser.close().catch(() => {});
    browser = null;
    context = null;
    tabs.clear();
    setTimeout(() => process.exit(0), 25);
    return { ok: true, shutdown: true };
  }

  if (cmd === 'new_tab') {
    const { id, page } = await getOrCreateTab(tabId);
    if (req.url) {
      if (!isUrlAllowedByWorker(req.url)) throw new Error('Blocked unsafe URL');
      await page.goto(req.url, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(350);
    }
    const snap = await captureTabSnapshot(page, true);
    return { ok: true, tab_id: id, ...snap };
  }

  if (cmd === 'close_tab') {
    const page = tabs.get(String(tabId));
    if (page && !page.isClosed()) {
      await page.close().catch(() => {});
    }
    tabs.delete(String(tabId));
    return { ok: true, tab_id: String(tabId), closed: true };
  }

  const { id, page } = await getOrCreateTab(tabId);

  if (cmd === 'switch_tab') {
    await page.bringToFront().catch(() => {});
    const snap = await captureTabSnapshot(page, true);
    return { ok: true, tab_id: id, ...snap };
  }

  if (cmd === 'navigate') {
    const url = String(req.url || '').trim();
    if (!isUrlAllowedByWorker(url)) throw new Error('Blocked unsafe URL');
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });
    await page.waitForTimeout(450);
    const snap = await captureTabSnapshot(page, true);
    return { ok: true, tab_id: id, ...snap };
  }

  if (cmd === 'click') {
    let clickX = typeof req.x === 'number' ? Math.max(0, Math.min(VIEWPORT.width - 1, Math.round(req.x))) : null;
    let clickY = typeof req.y === 'number' ? Math.max(0, Math.min(VIEWPORT.height - 1, Math.round(req.y))) : null;
    if (req.selector) {
      const loc = page.locator(String(req.selector)).first();
      const box = await loc.boundingBox().catch(() => null);
      if (box) {
        clickX = Math.round(box.x + box.width / 2);
        clickY = Math.round(box.y + box.height / 2);
      }
      await loc.click({ timeout: 8000 });
    } else if (req.text) {
      const loc = page.getByText(String(req.text), { exact: false }).first();
      const box = await loc.boundingBox().catch(() => null);
      if (box) {
        clickX = Math.round(box.x + box.width / 2);
        clickY = Math.round(box.y + box.height / 2);
      }
      await loc.click({ timeout: 8000 });
    } else if (clickX !== null && clickY !== null) {
      await page.mouse.move(clickX, clickY);
      await page.mouse.click(clickX, clickY);
    } else {
      throw new Error('click requires x/y, selector, or text');
    }
    await page.waitForTimeout(550);
    const snap = await captureTabSnapshot(page, true);
    return { ok: true, tab_id: id, coords: { x: clickX, y: clickY }, ...snap };
  }

  if (cmd === 'type') {
    const text = String(req.text || '');
    let clickX = typeof req.x === 'number' ? Math.max(0, Math.min(VIEWPORT.width - 1, Math.round(req.x))) : null;
    let clickY = typeof req.y === 'number' ? Math.max(0, Math.min(VIEWPORT.height - 1, Math.round(req.y))) : null;
    if (req.selector) {
      const loc = page.locator(String(req.selector)).first();
      const box = await loc.boundingBox().catch(() => null);
      if (box) {
        clickX = Math.round(box.x + box.width / 2);
        clickY = Math.round(box.y + box.height / 2);
      }
      await loc.click({ timeout: 8000 });
    } else if (clickX !== null && clickY !== null) {
      await page.mouse.click(clickX, clickY);
    }
    if (req.clear) {
      await page.keyboard.press('Control+A').catch(() => {});
      await page.keyboard.press('Backspace').catch(() => {});
    }
    await page.keyboard.type(text, { delay: 18 });
    if (req.submit) {
      await page.keyboard.press('Enter');
      await page.waitForTimeout(750);
    } else {
      await page.waitForTimeout(250);
    }
    const snap = await captureTabSnapshot(page, true);
    return { ok: true, tab_id: id, coords: clickX !== null ? { x: clickX, y: clickY } : null, ...snap };
  }

  if (cmd === 'press') {
    const key = String(req.key || 'Enter');
    await page.keyboard.press(key);
    await page.waitForTimeout(450);
    const snap = await captureTabSnapshot(page, true);
    return { ok: true, tab_id: id, ...snap };
  }

  if (cmd === 'scroll') {
    const deltaY = Number.isFinite(Number(req.delta_y)) ? Number(req.delta_y) : 420;
    const deltaX = Number.isFinite(Number(req.delta_x)) ? Number(req.delta_x) : 0;
    await page.mouse.wheel(deltaX, deltaY);
    await page.waitForTimeout(300);
    const snap = await captureTabSnapshot(page, true);
    return { ok: true, tab_id: id, ...snap };
  }

  if (cmd === 'back') {
    await page.goBack({ waitUntil: 'domcontentloaded', timeout: 12000 }).catch(() => {});
    await page.waitForTimeout(300);
    const snap = await captureTabSnapshot(page, true);
    return { ok: true, tab_id: id, ...snap };
  }

  if (cmd === 'forward') {
    await page.goForward({ waitUntil: 'domcontentloaded', timeout: 12000 }).catch(() => {});
    await page.waitForTimeout(300);
    const snap = await captureTabSnapshot(page, true);
    return { ok: true, tab_id: id, ...snap };
  }

  if (cmd === 'reload') {
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(350);
    const snap = await captureTabSnapshot(page, true);
    return { ok: true, tab_id: id, ...snap };
  }

  if (cmd === 'screenshot' || cmd === 'inspect') {
    const snap = await captureTabSnapshot(page, true);
    return { ok: true, tab_id: id, ...snap };
  }

  throw new Error(`Unknown command: ${cmd}`);
}

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });

rl.on('line', async (line) => {
  const trimmed = line.trim();
  if (!trimmed) return;
  let req;
  try {
    req = JSON.parse(trimmed);
  } catch (err) {
    process.stdout.write(JSON.stringify({ id: null, ok: false, error: 'Invalid JSON request' }) + '\n');
    return;
  }
  try {
    const result = await handleCommand(req);
    process.stdout.write(JSON.stringify({ id: req.id ?? null, ...result }) + '\n');
  } catch (err) {
    process.stdout.write(
      JSON.stringify({
        id: req.id ?? null,
        ok: false,
        error: err && err.message ? String(err.message) : String(err),
      }) + '\n'
    );
  }
});

process.on('SIGTERM', async () => {
  if (browser) await browser.close().catch(() => {});
  process.exit(0);
});
