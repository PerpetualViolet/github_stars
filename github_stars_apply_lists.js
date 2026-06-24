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
let USER = ARGS.user || process.env.GITHUB_STARS_USER || "";
const ORIGIN = "https://github.com";
const DELAY_MS = 800;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

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

async function browserPage() {
  const tabs = await getJson("http://127.0.0.1:9222/json/list");
  const tab = tabs.find((t) => t.type === "page" && t.url.startsWith(ORIGIN) && t.webSocketDebuggerUrl)
    || tabs.find((t) => t.type === "page" && t.webSocketDebuggerUrl);
  if (!tab) throw new Error("No Chrome page is available on port 9222.");
  const cdp = new Cdp(tab.webSocketDebuggerUrl);
  await cdp.connect();
  await cdp.send("Runtime.enable");
  return cdp;
}

async function evalPage(cdp, expression) {
  const { result, exceptionDetails } = await cdp.send("Runtime.evaluate", {
    awaitPromise: true,
    returnByValue: true,
    expression,
  });
  if (exceptionDetails) {
    throw new Error(exceptionDetails.text || "Runtime.evaluate failed");
  }
  return result.value;
}

function jsString(value) {
  return JSON.stringify(value);
}

async function ghFetch(cdp, url, options = {}) {
  return evalPage(cdp, `fetch(${jsString(url)}, ${JSON.stringify({
    credentials: "same-origin",
    redirect: "follow",
    ...options,
  })}).then(async r => ({
    ok: r.ok,
    status: r.status,
    url: r.url,
    text: await r.text()
  }))`);
}

async function ensureOnGithub(cdp) {
  const status = await evalPage(cdp, `(() => ({
    href: location.href,
    user: document.querySelector('meta[name="user-login"]')?.content || ''
  }))()`);
  if (!status.href.startsWith(ORIGIN)) {
    await cdp.send("Page.enable");
    await cdp.send("Page.navigate", { url: `${ORIGIN}/stars/${USER}` });
    await sleep(3000);
  }
  const user = await evalPage(cdp, `document.querySelector('meta[name="user-login"]')?.content || ''`);
  if (!user) throw new Error("Could not determine logged in GitHub user from the current browser session.");
  if (!USER) {
    USER = user;
    return;
  }
  if (user !== USER) throw new Error(`Expected logged in user ${USER}, got ${user || "(not signed in)"}.`);
}

function parseRepo(fullName) {
  const [owner, repo] = fullName.split("/");
  if (!owner || !repo) throw new Error(`Invalid repo name: ${fullName}`);
  return { owner, repo };
}

function extractInput(html, name) {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`<input[^>]+name=["']${escaped}["'][^>]*value=["']([^"']*)["']`, "i");
  return html.match(re)?.[1]?.replace(/&quot;/g, '"').replace(/&amp;/g, "&") || "";
}

function parseListsFragment(html) {
  const repositoryId = html.match(/data-repository-id="(\d+)"/)?.[1]
    || html.match(/name="repository_id" value="(\d+)"/)?.[1]
    || "";
  const updateUrl = html.match(/data-url="([^"]+)"/)?.[1] || "";
  const batchUrl = html.match(/data-batch-update-url="([^"]+)"/)?.[1] || "";
  const putToken = extractInput(html, "authenticity_token");
  const batchToken = html.match(/js-user-list-batch-update-csrf"[^>]+value="([^"]+)"/)?.[1] || "";
  const lists = [];
  const re = /<button\b[^>]*data-value="(\d+)"[^>]*aria-selected="(true|false)"[^>]*>[\s\S]*?<span[^>]*class="ActionListItem-label"[^>]*>\s*([\s\S]*?)\s*<\/span>/g;
  for (const match of html.matchAll(re)) {
    lists.push({
      id: match[1],
      selected: match[2] === "true",
      name: match[3].replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim(),
    });
  }
  return { repositoryId, updateUrl, batchUrl, putToken, batchToken, lists };
}

async function getRepoListState(cdp, fullName) {
  const { owner, repo } = parseRepo(fullName);
  const res = await ghFetch(cdp, `${ORIGIN}/${owner}/${repo}/lists?experimental=1`, {
    headers: { Accept: "text/html", "X-Requested-With": "XMLHttpRequest" },
  });
  if (!res.ok) throw new Error(`Failed to load list fragment for ${fullName}: HTTP ${res.status}`);
  const parsed = parseListsFragment(res.text);
  if (!parsed.repositoryId || !parsed.putToken || !parsed.updateUrl) {
    throw new Error(`Could not parse list state for ${fullName}`);
  }
  return parsed;
}

async function getCreateToken(cdp, fullName) {
  const { owner, repo } = parseRepo(fullName);
  const res = await ghFetch(cdp, `${ORIGIN}/${owner}/${repo}`, {
    headers: { Accept: "text/html" },
  });
  if (!res.ok) throw new Error(`Failed to load repo page ${fullName}: HTTP ${res.status}`);
  const formStart = res.text.indexOf(`action="/stars/${USER}/lists"`);
  if (formStart < 0) throw new Error(`Could not find create-list form for ${fullName}`);
  const snippet = res.text.slice(Math.max(0, formStart - 600), formStart + 5000);
  const token = extractInput(snippet, "authenticity_token");
  if (!token) throw new Error(`Could not parse create-list token for ${fullName}`);
  return token;
}

async function createList(cdp, list, repositoryId, token) {
  const form = new URLSearchParams();
  form.set("authenticity_token", token);
  form.set("repository_id", repositoryId);
  form.set("user_list[name]", list.name);
  form.set("user_list[description]", list.description || "");
  form.set("user_list[private]", "0");
  const res = await ghFetch(cdp, `${ORIGIN}/stars/${USER}/lists`, {
    method: "POST",
    headers: {
      Accept: "text/html, application/xhtml+xml",
      "Content-Type": "application/x-www-form-urlencoded",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: form.toString(),
  });
  if (![200, 201, 302].includes(res.status) && !res.ok) {
    throw new Error(`Failed to create list ${list.name}: HTTP ${res.status}\n${res.text.slice(0, 500)}`);
  }
  return res;
}

async function updateRepoLists(cdp, fullName, state, targetId) {
  return updateRepoListsExact(cdp, fullName, state, new Set([String(targetId)]), new Set());
}

async function updateRepoListsExact(cdp, fullName, state, desiredManagedIds, managedIds) {
  const ids = new Set();
  for (const list of state.lists) {
    const id = String(list.id);
    if (!list.selected) continue;
    if (managedIds.has(id)) continue;
    ids.add(id);
  }
  for (const id of desiredManagedIds) ids.add(String(id));
  const form = new URLSearchParams();
  form.set("_method", "put");
  form.set("authenticity_token", state.putToken);
  form.set("repository_id", state.repositoryId);
  form.set("context", "user_list_menu");
  for (const id of ids) form.append("list_ids[]", id);
  form.set("user_list_menu_dirty", "1");
  const res = await ghFetch(cdp, `${ORIGIN}${state.updateUrl}`, {
    method: "POST",
    headers: {
      Accept: "text/html, application/xhtml+xml",
      "Content-Type": "application/x-www-form-urlencoded",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: form.toString(),
  });
  if (!res.ok) {
    throw new Error(`Failed to update lists for ${fullName}: HTTP ${res.status}\n${res.text.slice(0, 500)}`);
  }
  return res;
}

function loadState() {
  if (!fs.existsSync(STATE_FILE)) {
    return { created: {}, assigned: {}, failures: [] };
  }
  return JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
}

function saveState(state) {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), "utf8");
}

async function main() {
  const data = JSON.parse(fs.readFileSync(CLASSIFICATION, "utf8"));
  const lists = data.lists;
  const repos = data.repositories;
  const byCategory = new Map();
  for (const repo of repos) {
    if (!byCategory.has(repo.category)) byCategory.set(repo.category, []);
    byCategory.get(repo.category).push(repo);
  }

  const state = loadState();
  const cdp = await browserPage();
  try {
    await ensureOnGithub(cdp);
    state.failures = [];

    const firstRepo = repos[0].full_name;
    let globalListState = await getRepoListState(cdp, firstRepo);
    const listIds = new Map(globalListState.lists.map((x) => [x.name, x.id]));

    console.log(`Existing lists: ${globalListState.lists.map((x) => `${x.name}=${x.id}`).join(", ") || "(none)"}`);

    for (const list of lists) {
      if (listIds.has(list.name)) {
        state.created[list.name] = listIds.get(list.name);
        continue;
      }
      const sample = byCategory.get(list.name)?.[0];
      if (!sample) {
        console.log(`SKIP create ${list.name}: no repository in category`);
        continue;
      }
      const repoState = await getRepoListState(cdp, sample.full_name);
      const token = await getCreateToken(cdp, sample.full_name);
      console.log(`Creating list: ${list.name} using ${sample.full_name}`);
      await createList(cdp, list, repoState.repositoryId, token);
      await sleep(DELAY_MS);
      const refreshed = await getRepoListState(cdp, sample.full_name);
      const created = refreshed.lists.find((x) => x.name === list.name);
      if (!created) throw new Error(`Created list ${list.name}, but could not find it afterwards.`);
      listIds.set(list.name, created.id);
      state.created[list.name] = created.id;
      state.assigned[`${sample.full_name} -> ${list.name}`] = true;
      saveState(state);
    }

    const managedIds = new Set(Object.values(state.created).map(String));
    let done = Object.keys(state.assigned).length;
    for (const repo of repos) {
      const targetId = state.created[repo.category] || listIds.get(repo.category);
      if (!targetId) throw new Error(`No list id for category ${repo.category}`);
      const key = `${repo.full_name} -> ${repo.category}`;
      if (state.assigned[key]) continue;
      try {
        const repoState = await getRepoListState(cdp, repo.full_name);
        const selectedManagedIds = new Set(
          repoState.lists.filter((x) => x.selected && managedIds.has(String(x.id))).map((x) => String(x.id))
        );
        const desiredManagedIds = new Set([String(targetId)]);
        const already = selectedManagedIds.size === desiredManagedIds.size
          && [...desiredManagedIds].every((id) => selectedManagedIds.has(id));
        if (!already) {
          try {
            await updateRepoListsExact(cdp, repo.full_name, repoState, desiredManagedIds, managedIds);
            await sleep(DELAY_MS);
          } catch (error) {
            // GitHub sometimes returns 406 to fetch-based updates even when the
            // list selection has already been applied. Re-read state before
            // recording a real failure.
            const refreshed = await getRepoListState(cdp, repo.full_name);
            const refreshedManagedIds = new Set(
              refreshed.lists.filter((x) => x.selected && managedIds.has(String(x.id))).map((x) => String(x.id))
            );
            const applied = refreshedManagedIds.size === desiredManagedIds.size
              && [...desiredManagedIds].every((id) => refreshedManagedIds.has(id));
            if (!applied) throw error;
          }
        }
        state.assigned[key] = true;
        done += 1;
        if (done % 10 === 0 || done === repos.length) {
          console.log(`Assigned ${done}/${repos.length}: ${repo.full_name} -> ${repo.category}`);
        }
        saveState(state);
      } catch (error) {
        const failure = { repo: repo.full_name, category: repo.category, error: error.message };
        state.failures.push(failure);
        saveState(state);
        console.log(`FAIL ${repo.full_name}: ${error.message}`);
      }
    }

    const uniqueFailures = state.failures.filter((f, i, arr) =>
      arr.findIndex((x) => x.repo === f.repo && x.category === f.category && x.error === f.error) === i
    );
    state.failures = uniqueFailures;
    saveState(state);
    console.log(`Done. Assigned records: ${Object.keys(state.assigned).length}/${repos.length}. Failures: ${state.failures.length}.`);
  } finally {
    cdp.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
