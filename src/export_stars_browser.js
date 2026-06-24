const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 1) {
    const part = argv[i];
    if (!part.startsWith("--")) continue;
    const key = part.slice(2);
    const value = argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[++i] : "true";
    args[key] = value;
  }
  return args;
}

const ARGS = parseArgs(process.argv);
const USER = ARGS.user || process.env.GITHUB_STARS_USER;
const OUTPUT = path.resolve(ARGS.output || "stars.browser.json");
const ORIGIN = "https://github.com";

function getJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => resolve(JSON.parse(data)));
    }).on("error", reject);
  });
}

class Cdp {
  constructor(url) {
    this.url = url;
    this.id = 1;
    this.pending = new Map();
  }
  async connect() {
    this.ws = new WebSocket(this.url);
    await new Promise((resolve, reject) => {
      this.ws.addEventListener("open", resolve, { once: true });
      this.ws.addEventListener("error", reject, { once: true });
    });
    this.ws.addEventListener("message", (event) => {
      const msg = JSON.parse(event.data);
      if (!msg.id || !this.pending.has(msg.id)) return;
      const pending = this.pending.get(msg.id);
      this.pending.delete(msg.id);
      msg.error ? pending.reject(new Error(msg.error.message)) : pending.resolve(msg.result);
    });
  }
  send(method, params = {}) {
    const id = this.id++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
  close() {
    this.ws?.close();
  }
}

async function evalPage(cdp, expression) {
  const { result, exceptionDetails } = await cdp.send("Runtime.evaluate", {
    awaitPromise: true,
    returnByValue: true,
    expression,
  });
  if (exceptionDetails) throw new Error(exceptionDetails.text || "Runtime.evaluate failed");
  return result.value;
}

async function ghFetch(cdp, relativeUrl) {
  return evalPage(
    cdp,
    `fetch(${JSON.stringify(relativeUrl)}, {
      credentials: 'same-origin',
      headers: { Accept: 'text/html' }
    }).then(async r => ({ status: r.status, html: await r.text() }))`
  );
}

async function parseCardsFromHtml(cdp, html) {
  return evalPage(
    cdp,
    `(() => {
      const html = ${JSON.stringify(html)};
      const doc = new DOMParser().parseFromString(html, 'text/html');
      const cards = [];
      const seen = new Set();
      const links = [...doc.querySelectorAll('h3 a[href^="/"]')];
      for (const link of links) {
        const item = link.closest('div.col-12') || link.closest('article') || link.parentElement?.parentElement;
        if (!link) continue;
        const href = link.getAttribute('href') || '';
        const full = href.replace(/^\\//, '').trim();
        if (!full || seen.has(full) || full.split('/').length !== 2) continue;
        seen.add(full);
        const description = item.querySelector('p')?.textContent?.replace(/\\s+/g, ' ').trim() || '';
        const language = item.querySelector('[itemprop="programmingLanguage"]')?.textContent?.replace(/\\s+/g, ' ').trim() || 'Unknown';
        const socialLinks = [...item.querySelectorAll('a.Link--muted, a[href$="/stargazers"], a[href$="/forks"]')];
        const numbers = socialLinks.map(a => (a.textContent || '').replace(/\\s+/g, ' ').trim()).filter(Boolean);
        const stars = Number((numbers[0] || '0').replace(/,/g, '')) || 0;
        const forks = Number((numbers[1] || '0').replace(/,/g, '')) || 0;
        cards.push({
          full_name: full,
          url: ${JSON.stringify(ORIGIN)} + '/' + full,
          description,
          language,
          stars,
          forks,
          topics: [],
          owner: full.split('/')[0],
          source: 'browser'
        });
      }
      return cards;
    })()`
  );
}

async function main() {
  if (!USER) throw new Error("GitHub user is required. Pass --user or set GITHUB_STARS_USER.");
  const tabs = await getJson("http://127.0.0.1:9222/json/list");
  const tab = tabs.find((t) => t.type === "page" && t.webSocketDebuggerUrl);
  if (!tab) throw new Error("No Chrome page available on port 9222.");
  const cdp = new Cdp(tab.webSocketDebuggerUrl);
  await cdp.connect();

  try {
    const repos = [];
    const seen = new Set();
    for (let page = 1; page <= 200; page += 1) {
      const res = await ghFetch(cdp, `/stars/${USER}/repositories?filter=all&page=${page}`);
      if (res.status !== 200) throw new Error(`Failed to load stars page ${page}: HTTP ${res.status}`);
      const cards = await parseCardsFromHtml(cdp, res.html);
      if (!cards.length) break;
      let newCount = 0;
      for (const card of cards) {
        if (seen.has(card.full_name)) continue;
        seen.add(card.full_name);
        repos.push(card);
        newCount += 1;
      }
      if (newCount === 0) break;
    }
    fs.writeFileSync(OUTPUT, JSON.stringify(repos, null, 2) + "\n", "utf8");
    console.log(JSON.stringify({ total: repos.length, output: OUTPUT }, null, 2));
  } finally {
    cdp.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
