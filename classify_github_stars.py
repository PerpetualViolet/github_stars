import csv
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "data" / "raw" / "stars.json"

CATEGORIES = [
    ("AI编程代理与Agent技能", "Codex/Claude/Cursor 等编码代理、agent harness、skills、MCP、上下文规划与多代理工作流。"),
    ("LLM接口代理与提示词", "OpenAI/Claude/Gemini 接口中转、免费模型资源、prompt 优化与提示词集合。"),
    ("AI创作-小说语音图像数字人", "网文/剧本写作、TTS/声音克隆、图像生成、数字分身与人格蒸馏。"),
    ("浏览器自动化与网页数据", "浏览器控制、Playwright/DevTools、网页抓取、搜索、爬虫、HTML/Markdown 数据抽取。"),
    ("文档Markdown与OCR", "PDF/Office/Markdown 转换、OCR、编辑器和文档处理工具。"),
    ("前端UI与设计系统", "React/Vue/UI 组件库、设计系统、动效、UI/UX skills 和前端框架。"),
    ("开发学习与开源清单", "编程学习、面试指南、GitHub 项目推荐、awesome 清单与课程资料。"),
    ("桌面效率与系统工具", "桌面端效率工具、远程桌面、下载器、系统监控、定时任务、账号/配置管理。"),
    ("Android移动与订阅规则", "Android/iOS/移动应用、无障碍点击、GKD/订阅规则、移动端 TTS。"),
    ("网络代理VPN与规则", "Clash/V2Ray/Shadowsocks/Trojan/Xray、代理池、GFW 规则、隧道和 VPN 客户端。"),
    ("影音动漫游戏工具", "动漫/E 站/视频音乐、游戏辅助、原神相关、娱乐内容工具。"),
    ("社交聊天与机器人工具", "QQ/Telegram/TikTok 等社交平台工具、聊天记录导出、机器人框架与自动化。"),
    ("安全-资产测绘与信息收集", "子域名、端口、空间测绘、资产发现、泄露监控和安全信息收集。"),
    ("安全-漏洞扫描POC与EXP", "漏洞扫描器、CVE/POC/EXP、框架漏洞利用、提权漏洞集合。"),
    ("安全-Burp Web测试与Fuzz", "Burp 插件、Web fuzz、WAF 指纹、CMS/WordPress 扫描、payload 速查。"),
    ("安全-红队免杀C2与Shellcode", "红队平台、免杀、shellcode、C2、payload 生成、钓鱼与攻防工具。"),
    ("安全-WebShell后渗透远控", "WebShell 管理、后渗透、远控/RAT、弱口令审计与代码混淆。"),
    ("安全-字典凭据与安全资料", "口令字典、默认凭据、安全思维导图、安全公众号和资料库。"),
    ("待人工确认", "描述或主题不足，建议打开仓库确认后再放入正式列表。"),
]

CATEGORY_DESC = dict(CATEGORIES)

RULES = [
    ("安全-WebShell后渗透远控", ["webshell", "antsword", "behinder", "godzilla", "rat", "remote administration", "远控", "后渗透", "弱口令", "ssdb", "代码混淆", "encryption project", "loader & keygen"]),
    ("安全-红队免杀C2与Shellcode", ["cobalt", "c2", "shellcode", "bypassav", "bypass-av", "免杀", "红队", "redteam", "red-team", "payload generator", "dll", "钓鱼", "phishing", "metasploit-shellcode", "filebinder", "trojan generator", "viper", "crossc2", "quasar"]),
    ("安全-Burp Web测试与Fuzz", ["burp", "fuzz", "wfuzz", "waf", "cms", "wordpress", "joomla", "drupal", "payload", "xss", "sqli", "xxe", "captcha", "webgoat", "web application", "wafw00f", "wpscan", "cmseek", "cmscan", "fuzzdb"]),
    ("安全-资产测绘与信息收集", ["subdomain", "asset", "资产", "fofa", "zoomeye", "quake", "shodan", "censys", "masscan", "nmap", "port scanner", "信息收集", "github leakage", "monitor", "泄露监控", "recon", "osint", "fingerprint", "指纹", "github rce/0day监控"]),
    ("安全-漏洞扫描POC与EXP", ["cve", "poc", "exp", "exploit", "漏洞", "vulnerability", "scanner", "scan", "shiro", "weblogic", "struts2", "metasploit framework", "kernel", "提权", "pocsuite", "vulmap", "xray", "wesng", "windows-exploit-suggester", "exploitdb"]),
    ("安全-字典凭据与安全资料", ["dictionary", "字典", "default credentials", "password", "security chart", "安全思维导图", "安全类公众号", "cheat-sheet", "pentesterspecialdict"]),
    ("网络代理VPN与规则", ["proxy", "vpn", "v2ray", "xray", "clash", "shadowsocks", "ssr", "trojan", "gfw", "gfwlist", "hysteria", "vmess", "vless", "wireguard", "frp", "tunnel", "pac", "freeproxy", "节点", "机场", "proxy_pool"]),
    ("AI编程代理与Agent技能", ["codex", "claude-code", "cursor", "antigravity", "kiro", "windsurf", "agent skill", "agent-skills", "skills", "mcp", "coding agent", "ai-coding", "code review graph", "context-engineering", "multi-agent", "agent harness", "opencode", "openclaw", "managed agents", "agentic", "superagent", "vibe coding", "claude plugin", "claude-skills"]),
    ("LLM接口代理与提示词", ["openai", "claude", "gemini", "llm", "gpt", "prompt", "ai-proxy", "model-router", "free-ai", "free-api", "inference", "api resources", "chatgpt2api", "sub2api", "openrelay", "prompt-optimizer", "prompts.chat"]),
    ("AI创作-小说语音图像数字人", ["novel", "writing", "writer", "tts", "voice", "clone", "image-generation", "gpt-image", "digital-avatar", "persona", "前任", "网文", "小说", "剧本", "声音", "语音", "sillytavern", "so-vits", "indextts", "weclone"]),
    ("浏览器自动化与网页数据", ["browser", "playwright", "chrome", "devtools", "crawler", "scraper", "scraping", "web-data", "data-extraction", "html-to-markdown", "firecrawl", "automation cli"]),
    ("文档Markdown与OCR", ["markdown", "pdf", "ocr", "office", "tesseract", "editor", "marktext", "document", "latex"]),
    ("前端UI与设计系统", ["ui", "ux", "design", "design-system", "react", "vue", "quasar", "shadcn", "tailwind", "gsap", "component", "frontend", "landing-page", "figma", "uikit"]),
    ("开发学习与开源清单", ["javaguide", "interview", "course", "tutorial", "awesome", "awesome-list", "hellogithub", "learning", "guide", "开源项目", "面试", "课程"]),
    ("Android移动与订阅规则", ["android", "kotlin", "ios", "mobile", "apk", "gkd", "subscription", "accessibility", "tts-server-android", "wake on lan application for android"]),
    ("桌面效率与系统工具", ["desktop", "remote-desktop", "download", "downloader", "aria2", "gopeed", "steam", "trafficmonitor", "wakeonlan", "task-manager", "crontab", "account-manager", "idm", "music-player", "rustdesk", "watt toolkit"]),
    ("影音动漫游戏工具", ["anime", "age", "ehentai", "e-hentai", "ehviewer", "tiktok", "genshin", "yuanshen", "music", "listen1", "video", "ffmpeg", "comic", "cartoon", "game", "steamtools", "model importer"]),
    ("社交聊天与机器人工具", ["qqbot", "qqrobot", "coolq", "cqhttp", "telegram", "chat-export", "qq聊天", "tiktok"]),
]

OVERRIDES = {
    "microsoft/markitdown": "文档Markdown与OCR",
    "ocrmypdf/OCRmyPDF": "文档Markdown与OCR",
    "marktext/marktext": "文档Markdown与OCR",
    "FFmpeg/FFmpeg": "影音动漫游戏工具",
    "openai/whisper": "AI创作-小说语音图像数字人",
    "rustdesk/rustdesk": "桌面效率与系统工具",
    "GopeedLab/gopeed": "桌面效率与系统工具",
    "aria2/aria2": "桌面效率与系统工具",
    "quasarframework/quasar": "前端UI与设计系统",
    "shadcn-ui/ui": "前端UI与设计系统",
    "listen1/listen1_desktop": "影音动漫游戏工具",
    "BeyondDimension/SteamTools": "影音动漫游戏工具",
    "phoboslab/qoi": "待人工确认",
    "ghealer/GUI_Tools": "待人工确认",
    "Snailclimb/JavaGuide": "开发学习与开源清单",
    "521xueweihan/HelloGitHub": "开发学习与开源清单",
    "datawhalechina/easy-vibe": "开发学习与开源清单",
    "2025Emma/vibe-coding-cn": "开发学习与开源清单",
    "fatedier/frp": "网络代理VPN与规则",
    "jhao104/proxy_pool": "网络代理VPN与规则",
    "Wei-Shaw/sub2api": "LLM接口代理与提示词",
    "romgX/openrelay": "LLM接口代理与提示词",
    "clash-verge-rev/clash-verge-rev": "网络代理VPN与规则",
    "hiddify/hiddify-app": "网络代理VPN与规则",
    "Loyalsoldier/v2ray-rules-dat": "网络代理VPN与规则",
    "2dust/v2rayNG": "网络代理VPN与规则",
    "2dust/v2rayN": "网络代理VPN与规则",
    "proxysu/ProxySU": "网络代理VPN与规则",
    "FoundationAgents/MetaGPT": "AI编程代理与Agent技能",
    "BigPizzaV3/CodexPlusPlus": "AI编程代理与Agent技能",
    "garrytan/gstack": "AI编程代理与Agent技能",
    "vercel-labs/agent-browser": "浏览器自动化与网页数据",
    "firecrawl/firecrawl": "浏览器自动化与网页数据",
    "browser-use/browser-use": "浏览器自动化与网页数据",
    "jlcodes99/cockpit-tools": "桌面效率与系统工具",
    "nextlevelbuilder/ui-ux-pro-max-skill": "前端UI与设计系统",
    "greensock/gsap-skills": "前端UI与设计系统",
    "VoltAgent/awesome-design-md": "前端UI与设计系统",
    "SillyTavern/SillyTavern": "AI创作-小说语音图像数字人",
    "worldwonderer/oh-story-claudecode": "AI创作-小说语音图像数字人",
    "lingfengQAQ/webnovel-writer": "AI创作-小说语音图像数字人",
    "RVC-Boss/GPT-SoVITS": "AI创作-小说语音图像数字人",
    "xming521/WeClone": "AI创作-小说语音图像数字人",
    "Narcooo/inkos": "AI创作-小说语音图像数字人",
    "wfcz10086/AI-automatically-generates-novels": "AI创作-小说语音图像数字人",
    "xixu-me/awesome-persona-distill-skills": "AI创作-小说语音图像数字人",
    "EvoLinkAI/awesome-gpt-image-2-API-and-Prompts": "AI创作-小说语音图像数字人",
    "fangzesheng/free-api": "开发学习与开源清单",
    "bilibili/ailab": "AI创作-小说语音图像数字人",
    "OpenEthan/SMSBoom": "安全-红队免杀C2与Shellcode",
    "qq8e/qq": "安全-字典凭据与安全资料",
    "shuakami/qq-chat-exporter": "社交聊天与机器人工具",
    "Mrs4s/go-cqhttp": "社交聊天与机器人工具",
    "FloatTech/gocqzbp": "社交聊天与机器人工具",
    "FloatTech/ZeroBot-Plugin": "社交聊天与机器人工具",
    "huiyadanli/RevokeMsgPatcher": "社交聊天与机器人工具",
    "Mr-xn/sunlogin_rce": "安全-漏洞扫描POC与EXP",
    "qazbnm456/awesome-cve-poc": "安全-漏洞扫描POC与EXP",
    "scipag/vulscan": "安全-漏洞扫描POC与EXP",
    "frohoff/ysoserial": "安全-漏洞扫描POC与EXP",
    "WebGoat/WebGoat": "安全-Burp Web测试与Fuzz",
    "JDWXX/jd_job": "桌面效率与系统工具",
    "M2TeamArchived/NSudo": "桌面效率与系统工具",
    "koodo-reader/koodo-reader": "桌面效率与系统工具",
    "gkd-kit/gkd": "Android移动与订阅规则",
    "jing332/tts-server-android": "Android移动与订阅规则",
    "ehang-io/nps": "网络代理VPN与规则",
    "babalae/better-genshin-impact": "影音动漫游戏工具",
    "MatrixTM/MHDDoS": "安全-红队免杀C2与Shellcode",
    "ComposioHQ/awesome-claude-skills": "AI编程代理与Agent技能",
    "wgpsec/CreateHiddenAccount": "安全-红队免杀C2与Shellcode",
}


def classify(repo):
    full_name = repo.get("full_name") or ""
    if full_name in OVERRIDES:
        return OVERRIDES[full_name], "manual"

    text = " ".join([
        full_name,
        repo.get("owner") or "",
        repo.get("language") or "",
        repo.get("description") or "",
        " ".join(repo.get("topics") or []),
    ]).lower()
    text = re.sub(r"[-_/\\.]+", " ", text)

    for category, keywords in RULES:
        for keyword in keywords:
            if keyword.lower() in text:
                return category, keyword
    return "待人工确认", ""


def build_outputs(data, source_path):
    order = [name for name, _ in CATEGORIES]
    items = []
    by_category = defaultdict(list)

    for repo in data:
        category, reason = classify(repo)
        record = {
            "category": category,
            "full_name": repo.get("full_name"),
            "url": repo.get("url"),
            "description": repo.get("description") or "",
            "language": repo.get("language") or "Unknown",
            "stars": repo.get("stars") or 0,
            "topics": repo.get("topics") or [],
            "reason": reason,
            "list_description": CATEGORY_DESC[category],
        }
        items.append(record)
        by_category[category].append(record)

    for repos in by_category.values():
        repos.sort(key=lambda item: (-int(item["stars"]), item["full_name"].lower()))

    return items, by_category


def write_outputs(items, by_category, source_path, output_dir):
    order = [name for name, _ in CATEGORIES]
    output_dir.mkdir(parents=True, exist_ok=True)
    md = [
        "# GitHub Stars 分类建议",
        "",
        f"数据源: `{source_path.name}`",
        f"仓库总数: {len(items)}",
        "",
        "## 建议创建的 GitHub Lists",
        "",
        "| List 名称 | 数量 | 一眼看懂的描述 |",
        "|---|---:|---|",
    ]
    for category in order:
        if category in by_category:
            md.append(f"| {category} | {len(by_category[category])} | {CATEGORY_DESC[category]} |")

    md.extend(["", "## 仓库归类明细"])
    for category in order:
        repos = by_category.get(category)
        if not repos:
            continue
        md.extend(["", f"### {category} ({len(repos)})", "", CATEGORY_DESC[category], ""])
        for repo in repos:
            desc = (repo["description"] or "").replace("|", "\\|").replace("\n", " ")
            if len(desc) > 130:
                desc = desc[:127] + "..."
            topics = ", ".join(repo["topics"][:6])
            extra = f" topics: {topics}" if topics else ""
            md.append(f"- [{repo['full_name']}]({repo['url']}) | {repo['language']} | stars {repo['stars']} | {desc}{extra}")

    (output_dir / "github_stars_classification.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (output_dir / "github_stars_classification.json").write_text(
        json.dumps(
            {
                "source": str(source_path),
                "total": len(items),
                "lists": [
                    {
                        "name": category,
                        "description": CATEGORY_DESC[category],
                        "count": len(by_category.get(category, [])),
                    }
                    for category in order
                    if category in by_category
                ],
                "repositories": items,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with (output_dir / "github_stars_classification.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["category", "full_name", "url", "language", "stars", "topics", "description", "reason"],
        )
        writer.writeheader()
        for repo in items:
            writer.writerow(
                {
                    "category": repo["category"],
                    "full_name": repo["full_name"],
                    "url": repo["url"],
                    "language": repo["language"],
                    "stars": repo["stars"],
                    "topics": ",".join(repo["topics"]),
                    "description": repo["description"],
                    "reason": repo["reason"],
                }
            )

    for item in json.loads((output_dir / "github_stars_classification.json").read_text(encoding="utf-8"))["lists"]:
        print(f"{item['name']}: {item['count']}")


def parse_args():
    parser = argparse.ArgumentParser(description="Classify GitHub stars into curated lists.")
    parser.add_argument("--input", type=Path, default=SOURCE, help="Path to normalized stars JSON.")
    parser.add_argument("--output-dir", type=Path, default=BASE_DIR / "data" / "classification", help="Directory for classification outputs.")
    return parser.parse_args()


def main():
    args = parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    items, by_category = build_outputs(data, args.input)
    write_outputs(items, by_category, args.input, args.output_dir)


if __name__ == "__main__":
    main()
