#!/usr/bin/env python3
"""
GitHub Daily Report Generator — CI 版
在 GitHub Actions 中运行，从环境变量获取 Token 和 Webhook
"""

import json
import os
import re
import subprocess
from datetime import datetime, timedelta

REPO_DIR = os.getcwd()
API_BASE = "https://api.github.com"
TODAY = datetime.now().strftime("%Y-%m-%d")
WEEK_AGO = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
REPORT_FILE = f"GitHub_Weekly_Report_{datetime.now().strftime('%Y%m%d')}.md"

# 从环境变量读取（由 GitHub Secrets 注入）
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def api_get(url):
    try:
        r = subprocess.run(["curl", "-sf", url], capture_output=True, text=True, timeout=30)
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout else None
    except Exception as e:
        log(f"API 请求失败: {e}")
        return None


def repo_info(name):
    return api_get(f"{API_BASE}/repos/{name}")


def fetch_trending():
    try:
        r = subprocess.run(
            ["curl", "-sfL", "https://github.com/trending?since=weekly"],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0:
            return []
        repos = re.findall(r'href="/"([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)"', r.stdout)
        seen = set()
        return [x for x in repos if x not in seen and not seen.add(x)]
    except Exception as e:
        log(f"Trending 失败: {e}")
        return []


def main():
    log(f"开始生成报告 ({TODAY})")

    all_time = api_get(f"{API_BASE}/search/repositories?q=stars:%3E100000&sort=stars&order=desc&per_page=15")
    new_week = api_get(f"{API_BASE}/search/repositories?q=created:%3E{WEEK_AGO}&sort=stars&order=desc&per_page=30")
    trending = fetch_trending()

    lines = []
    lines.append("# GitHub 近一周项目分析报告\n")
    lines.append(f"**报告日期：** {TODAY}（数据截至当日 UTC+8）  ")
    lines.append("**数据来源：** GitHub API + GitHub Trending (Weekly)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- 全历史 Top 10 ----
    lines.append("## 第一部分：总 Star 排名前十（全历史累计）\n")
    lines.append("| # | 项目 | Stars | 语言 | 简介 |")
    lines.append("|---|------|------:|------|------|")
    if all_time and "items" in all_time:
        for i, r in enumerate(all_time["items"][:10], 1):
            n = r["full_name"]
            s = f"{r['stargazers_count']:,}"
            l = r.get("language") or "-"
            d = (r.get("description") or "")[:70]
            lines.append(f"| {i} | **[{n}](https://github.com/{n})** | {s} | {l} | {d} |")
    lines.append("")

    # ---- 本周新星 ----
    lines.append("---\n")
    lines.append("## 第二部分：本周 Star 增长排名\n")
    lines.append("### 2.1 本周新星爆发榜（本周新创建项目）\n")
    lines.append("| # | 项目 | Stars | 语言 | 简介 |")
    lines.append("|---|------|------:|------|------|")
    if new_week and "items" in new_week:
        for i, r in enumerate(new_week["items"][:15], 1):
            n = r["full_name"]
            s = f"{r['stargazers_count']:,}"
            l = r.get("language") or "N/A"
            d = (r.get("description") or "")[:60]
            lines.append(f"| {i} | **[{n}](https://github.com/{n})** | {s} | {l} | {d} |")
    lines.append("")

    # ---- Trending 周榜 ----
    lines.append("### 2.2 本周 Trending（成熟项目，周受关注度最高）\n")
    lines.append("| # | 项目 | Stars | 语言 | 简介 |")
    lines.append("|---|------|------:|------|------|")
    for i, repo in enumerate(trending[:15], 1):
        info = repo_info(repo)
        if info:
            s = f"{info.get('stargazers_count', 0):,}"
            l = info.get("language") or "N/A"
            d = (info.get("description") or "")[:60]
        else:
            s, l, d = "?", "?", ""
        lines.append(f"| {i} | **[{repo}](https://github.com/{repo})** | {s} | {l} | {d} |")
    lines.append("")

    lines.append("---\n")
    lines.append("## 第三部分：趋势解读\n")
    lines.append("*趋势分析由脚本自动生成，可根据热点动态编辑。*\n")
    lines.append("---\n")
    lines.append(f"*报告由 GitHub Actions 每日自动生成，数据截止 {TODAY}。*\n")

    content = "\n".join(lines)

    report_path = os.path.join(REPO_DIR, REPORT_FILE)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(content)
    log(f"报告写入: {report_path}")

    # 飞书推送
    if FEISHU_WEBHOOK:
        import urllib.request
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
                    {
                        "tag": "note",
                        "elements": [{"tag": "plain_text", "content": "GitHub Daily Report Bot · 自动推送"}]
                    }
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
