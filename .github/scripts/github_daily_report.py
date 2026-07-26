#!/usr/bin/env python3
"""
GitHub Daily Report Generator — CI 版
"""

import json, os, re, subprocess, urllib.request
from datetime import datetime, timedelta, timezone

# 强制北京时间
BEIJING = timezone(timedelta(hours=8))
TODAY = datetime.now(BEIJING).strftime("%Y-%m-%d")
WEEK_AGO = (datetime.now(BEIJING) - timedelta(days=7)).strftime("%Y-%m-%d")
REPORT_FILE = f"GitHub_Weekly_Report_{datetime.now(BEIJING).strftime('%Y%m%d')}.md"

REPO_DIR = os.getcwd()
API_BASE = "https://api.github.com"
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")


def log(msg):
    print(f"[{datetime.now(BEIJING).strftime('%H:%M:%S')}] {msg}")


def api_get(url):
    try:
        r = subprocess.run(["curl", "-sf", url], capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout:
            return json.loads(r.stdout)
        return None
    except Exception as e:
        log(f"API 请求失败: {e}")
        return None


def repo_info(name):
    """获取仓库信息，返回 dict 或 None"""
    data = api_get(f"{API_BASE}/repos/{name}")
    if isinstance(data, dict):
        return data
    return None


def fetch_trending():
    """获取 GitHub Trending 周榜，返回有效的 owner/repo 列表"""
    try:
        r = subprocess.run(
            ["curl", "-sfL", "https://github.com/trending?since=weekly"],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0:
            return []

        html = r.stdout
        # 匹配 h2 标签中的 repo 链接，只匹配 owner/repo 格式
        repos = []
        for match in re.finditer(r'<h2[^>]*>.*?<a[^>]*href="/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)"', html, re.DOTALL):
            repo = match.group(1)
            # 过滤掉非仓库链接
            if not repo.startswith("sponsors/") and not repo.startswith("trending/"):
                repos.append(repo)

        seen = set()
        return [x for x in repos if x not in seen and not seen.add(x)]
    except Exception as e:
        log(f"Trending 失败: {e}")
        return []


def build_report(all_time, new_week, trending):
    """生成报告内容"""
    lines = []

    # --- 标题 ---
    lines += [
        "# GitHub 近一周项目分析报告\n",
        f"**报告日期：** {TODAY}（北京时间）  ",
        "**数据来源：** GitHub API + GitHub Trending (Weekly)",
        "",
        "---",
        "",
    ]

    # --- Part 1: 全历史 Top 10 ---
    lines += [
        "## 第一部分：总 Star 排名前十（全历史累计）\n",
        "| # | 项目 | Stars | 语言 | 简介 |",
        "|---|------|------:|------|------|",
    ]
    if isinstance(all_time, dict) and "items" in all_time:
        for i, r in enumerate(all_time["items"][:10], 1):
            n = r["full_name"]
            s = f"{r['stargazers_count']:,}"
            l = r.get("language") or "-"
            d = (r.get("description") or "")[:70]
            lines.append(f"| {i} | **[{n}](https://github.com/{n})** | {s} | {l} | {d} |")

    # --- Part 2: 本周之星 ---
    lines += [
        "",
        "---",
        "",
        "## 第二部分：本周 Star 增长排名\n",
        "### 2.1 本周新星爆发榜（本周新创建项目）\n",
        "| # | 项目 | Stars | 语言 | 简介 |",
        "|---|------|------:|------|------|",
    ]
    if isinstance(new_week, dict) and "items" in new_week:
        for i, r in enumerate(new_week["items"][:15], 1):
            n = r["full_name"]
            s = f"{r['stargazers_count']:,}"
            l = r.get("language") or "N/A"
            d = (r.get("description") or "")[:60]
            lines.append(f"| {i} | **[{n}](https://github.com/{n})** | {s} | {l} | {d} |")

    lines += [
        "",
        "### 2.2 本周 Trending（成熟项目，周受关注度最高）\n",
        "| # | 项目 | Stars | 语言 | 简介 |",
        "|---|------|------:|------|------|",
    ]
    for i, repo in enumerate(trending[:15], 1):
        info = repo_info(repo)
        if isinstance(info, dict):
            s = f"{info.get('stargazers_count', 0):,}"
            l = info.get("language") or "N/A"
            d = (info.get("description") or "")[:60]
        else:
            s, l, d = "?", "?", ""
        lines.append(f"| {i} | **[{repo}](https://github.com/{repo})** | {s} | {l} | {d} |")

    # --- 趋势分析 ---
    lines += ["", "---", "", "## 第三部分：趋势解读\n"]

    # 统计关键词
    all_names = []
    if isinstance(all_time, dict) and "items" in all_time:
        for r in all_time["items"][:10]:
            all_names.append((r["full_name"], r.get("description","") or ""))
    if isinstance(new_week, dict) and "items" in new_week:
        for r in new_week["items"][:10]:
            all_names.append((r["full_name"], r.get("description","") or ""))

    ai_agent_count = sum(1 for _,d in all_names if "agent" in d.lower() or "ai" in d.lower())
    learning_count = sum(1 for _,d in all_names if "book" in d.lower() or "learn" in d.lower() or "course" in d.lower() or "study" in d.lower() or "guide" in d.lower())

    if ai_agent_count > 5:
        lines.append("### AI Agent 持续主导\n")
        lines.append("本周项目中 AI/Agent 相关项目占比突出，涵盖编码 Agent、多 Agent 协作框架、端侧推理等多个方向，")
        lines.append("反映 AI Agent 正从概念走向工具化落地。\n")
    if learning_count > 3:
        lines.append("### 学习资源类项目依旧坚挺\n")
        lines.append("全历史 Star 榜中学习资源类项目持续霸榜，build-your-own-x、freeCodeCamp、system-design-primer 等")
        lines.append("仍是开发者社区最认可的知识沉淀。\n")
    lines.append("")
    lines.append("*详细趋势分析可根据每周热点手动补充。*\n")

    # --- 语言分布统计 ---
    lang_counts = {}

    if isinstance(all_time, dict) and "items" in all_time:
        for r in all_time["items"][:10]:
            l = r.get("language")
            if l:
                lang_counts[l] = lang_counts.get(l, 0) + 1
    if isinstance(new_week, dict) and "items" in new_week:
        for r in new_week["items"][:15]:
            l = r.get("language")
            if l:
                lang_counts[l] = lang_counts.get(l, 0) + 1
    for repo in trending[:15]:
        info = repo_info(repo)
        if isinstance(info, dict):
            l = info.get("language")
            if l:
                lang_counts[l] = lang_counts.get(l, 0) + 1

    lines += [
        "",
        "---",
        "",
        "## 第四部分：语言分布统计\n",
        "| 语言 | 项目数 |",
        "|------|:------:|",
    ]
    for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1])[:10]:
        lines.append(f"| {lang} | {count} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"Python 和 TypeScript 在 AI 项目中占比最高，Rust 则多见于性能敏感的工具链层。")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*本报告由 GitHub Actions 每日自动生成，数据截止 {TODAY}。*\n")

    return "\n".join(lines)


def main():
    log(f"开始生成报告 ({TODAY})")

    all_time = api_get(f"{API_BASE}/search/repositories?q=stars:%3E100000&sort=stars&order=desc&per_page=15")
    new_week = api_get(f"{API_BASE}/search/repositories?q=created:%3E{WEEK_AGO}&sort=stars&order=desc&per_page=30")
    trending = fetch_trending()

    log(f"Trending 获取到 {len(trending)} 个仓库")

    content = build_report(all_time, new_week, trending)

    report_path = os.path.join(REPO_DIR, REPORT_FILE)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(content)
    log(f"报告写入: {REPORT_FILE}")

    # --- 飞书推送 ---
    if FEISHU_WEBHOOK:
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"📊 GitHub 每周项目报告 ({TODAY})"},
                    "template": "indigo"
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": f"**报告已更新**\n📅 数据截止：{TODAY}\n\n👉 [查看完整报告](https://github.com/GeneElias/Notes/blob/main/{REPORT_FILE})"
                    },
                    {"tag": "hr"},
                    {"tag": "note", "elements": [{"tag": "plain_text", "content": "GitHub Daily Report Bot · 自动推送"}]}
                ]
            }
        }
        try:
            data = json.dumps(card).encode()
            req = urllib.request.Request(FEISHU_WEBHOOK, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
            log("飞书推送成功")
        except Exception as e:
            log(f"飞书推送失败: {e}")
    else:
        log("飞书未配置，跳过推送")

    log("全部完成！")


if __name__ == "__main__":
    main()
