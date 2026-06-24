const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

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
const ROOT = process.cwd();
const CLASSIFICATION = path.resolve(ARGS.classification || path.join(ROOT, "data", "classification", "github_stars_classification.json"));
const STATE_FILE = path.resolve(ARGS.state || path.join(ROOT, "data", "audit", "list_sync_state.json"));
const REPORT_FILE = path.resolve(ARGS.report || path.join(ROOT, "data", "audit", "list_audit_report.json"));
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

function parseSelectedListIds(html) {
  return [...html.matchAll(/data-value="(\d+)"[^>]*aria-selected="true"/g)].map((m) => m[1]);
}

async function main() {
  const data = JSON.parse(fs.readFileSync(CLASSIFICATION, "utf8"));
  const state = JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
  const tabs = await getJson("http://127.0.0.1:9222/json/list");
  const tab = tabs.find((t) => t.type === "page" && t.url.startsWith(ORIGIN) && t.webSocketDebuggerUrl)
    || tabs.find((t) => t.type === "page" && t.webSocketDebuggerUrl);
  if (!tab) throw new Error("No Chrome page available.");
  const cdp = new Cdp(tab.webSocketDebuggerUrl);
  await cdp.connect();
  await cdp.send("Runtime.enable");

  const ok = [];
  const missing = [];
  const errors = [];

  for (const repo of data.repositories) {
    const targetId = state.created[repo.category];
    try {
      const { result } = await cdp.send("Runtime.evaluate", {
        awaitPromise: true,
        returnByValue: true,
        expression: `fetch('/${repo.full_name}/lists?experimental=1', {
          credentials: 'same-origin',
          headers: { Accept: 'text/html', 'X-Requested-With': 'XMLHttpRequest' }
        }).then(async r => ({ status: r.status, text: await r.text() }))`,
      });
      const value = result.value;
      if (value.status !== 200) {
        errors.push({ repo: repo.full_name, category: repo.category, status: value.status });
        continue;
      }
      const selected = parseSelectedListIds(value.text);
      const entry = { repo: repo.full_name, category: repo.category, targetId, selected };
      if (selected.includes(targetId)) ok.push(entry);
      else missing.push(entry);
    } catch (error) {
      errors.push({ repo: repo.full_name, category: repo.category, error: error.message });
    }
  }

  const report = {
    total: data.repositories.length,
    ok: ok.length,
    missing: missing.length,
    errors: errors.length,
    missingRepos: missing,
    errorRepos: errors
  };
  fs.writeFileSync(REPORT_FILE, JSON.stringify(report, null, 2), "utf8");
  console.log(JSON.stringify(report, null, 2));
  cdp.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
