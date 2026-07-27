#!/usr/bin/env python3
"""
GitHub Daily Report Generator — 生成报告 → GitHub 推送 → 飞书文档
"""

import json, os, re, subprocess, urllib.request
from datetime import datetime, timedelta, timezone

BEIJING = timezone(timedelta(hours=8))
TODAY = datetime.now(BEIJING).strftime("%Y-%m-%d")
WEEK_AGO = (datetime.now(BEIJING) - timedelta(days=7)).strftime("%Y-%m-%d")
REPORT_FILE = f"GitHub_Weekly_Report_{datetime.now(BEIJING).strftime('%Y%m%d')}.md"

REPO_DIR = os.getcwd()
API_BASE = "https://api.github.com"

# 从环境变量读取（GitHub Secrets → Actions env）
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")


def log(msg):
    print(f"[{datetime.now(BEIJING).strftime('%H:%M:%S')}] {msg}")


# ═══ GitHub API ═══

def api_get(url):
    try:
        r = subprocess.run(["curl", "-sf", url], capture_output=True, text=True, timeout=30)
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout else None
    except:
        return None


def repo_info(name):
    data = api_get(f"{API_BASE}/repos/{name}")
    return data if isinstance(data, dict) else None


def fetch_trending():
    try:
        r = subprocess.run(
            ["curl", "-sfL", "https://github.com/trending?since=weekly"],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0:
            return []
        repos = []
        for m in re.finditer(r'<h2[^>]*>.*?<a[^>]*href="/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)"', r.stdout, re.DOTALL):
            repo = m.group(1)
            if not repo.startswith("sponsors/") and not repo.startswith("trending/"):
                repos.append(repo)
        seen = set()
        return [x for x in repos if x not in seen and not seen.add(x)]
    except:
        return []


# ═══ 报告生成 ═══

def build_report(all_time, new_week, trending):
    lines = []
    lines += ["# GitHub 近一周项目分析报告\n", f"**报告日期：** {TODAY}（北京时间）  ", "**数据来源：** GitHub API + GitHub Trending (Weekly)", "", "---", ""]

    lines += ["## 第一部分：总 Star 排名前十（全历史累计）\n", "| # | 项目 | Stars | 语言 | 简介 |", "|---|------|------:|------|------|"]
    if isinstance(all_time, dict) and "items" in all_time:
        for i, r in enumerate(all_time["items"][:10], 1):
            lines.append(f"| {i} | **[{r['full_name']}](https://github.com/{r['full_name']})** | {r['stargazers_count']:,} | {r.get('language') or '-'} | {(r.get('description') or '')[:70]} |")
    lines += ["", "---", "", "## 第二部分：本周 Star 增长排名\n", "### 2.1 本周新星爆发榜\n", "| # | 项目 | Stars | 语言 | 简介 |", "|---|------|------:|------|------|"]
    if isinstance(new_week, dict) and "items" in new_week:
        for i, r in enumerate(new_week["items"][:15], 1):
            lines.append(f"| {i} | **[{r['full_name']}](https://github.com/{r['full_name']})** | {r['stargazers_count']:,} | {r.get('language') or 'N/A'} | {(r.get('description') or '')[:60]} |")
    lines += ["", "### 2.2 本周 Trending\n", "| # | 项目 | Stars | 语言 | 简介 |", "|---|------|------:|------|------|"]
    for i, repo in enumerate(trending[:15], 1):
        info = repo_info(repo)
        if isinstance(info, dict):
            s = f"{info.get('stargazers_count', 0):,}"
            l = info.get("language") or "N/A"
            d = (info.get("description") or "")[:60]
        else:
            s, l, d = "?", "?", ""
        lines.append(f"| {i} | **[{repo}](https://github.com/{repo})** | {s} | {l} | {d} |")
    lines += ["", "---", "", "## 第三部分：趋势解读\n", "*报告基于全历史 Top 10 和本周新兴项目自动生成趋势分析，可根据热点动态补充。*\n", "---", "", "## 第四部分：语言分布统计\n"]
    lang_counts = {}
    for src in [all_time, new_week]:
        if isinstance(src, dict) and "items" in src:
            for r in src["items"][:15]:
                l = r.get("language")
                if l: lang_counts[l] = lang_counts.get(l, 0) + 1
    for repo in trending[:15]:
        info = repo_info(repo)
        if isinstance(info, dict):
            l = info.get("language")
            if l: lang_counts[l] = lang_counts.get(l, 0) + 1
    lines += ["| 语言 | 项目数 |", "|------|:------:|"]
    for lang, c in sorted(lang_counts.items(), key=lambda x: -x[1])[:10]:
        lines.append(f"| {lang} | {c} |")
    lines += ["", "---", "", f"*本报告由 GitHub Actions 每日自动生成，数据截止 {TODAY}。*\n"]
    return "\n".join(lines)


# ═══ 飞书文档 ═══

def feishu_request(method, path, token=None, data=None):
    """调用飞书 API"""
    url = f"https://open.feishu.cn/open-apis{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read()) if e.code != 204 else {"code": -1, "msg": str(e)}
    except Exception as e:
        return {"code": -1, "msg": str(e)}


def get_feishu_token():
    """获取飞书 tenant access token"""
    resp = feishu_request("POST", "/auth/v3/tenant_access_token/internal", data={
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    })
    if resp.get("code") == 0:
        return resp["tenant_access_token"]
    log(f"飞书 Token 获取失败: {resp.get('msg','')}")
    return None


def create_feishu_doc(token, title):
    """创建飞书文档"""
    resp = feishu_request("POST", "/docx/v1/documents", token=token, data={"title": title})
    if resp.get("code") == 0:
        doc_id = resp["data"]["document"]["document_id"]
        log(f"飞书文档已创建: {doc_id}")
        return doc_id
    log(f"飞书文档创建失败: {resp.get('msg','')}")
    return None


def md_line_to_feishu_blocks(line):
    """将一行 Markdown 转为飞书 block（列表，可能为 0~1 个元素）"""
    stripped = line.strip()

    # 空行跳过
    if not stripped:
        return []

    # 分隔线
    if stripped == "---":
        return [{"block_type": 22, "divider": {}}]

    # 标题
    if stripped.startswith("#### "):
        return [{"block_type": 5, "heading3": {"elements": parse_inline(stripped[5:]), "style": {}}}]
    if stripped.startswith("### "):
        return [{"block_type": 5, "heading3": {"elements": parse_inline(stripped[4:]), "style": {}}}]
    if stripped.startswith("## "):
        return [{"block_type": 4, "heading2": {"elements": parse_inline(stripped[3:]), "style": {}}}]
    if stripped.startswith("# "):
        return [{"block_type": 3, "heading1": {"elements": parse_inline(stripped[2:]), "style": {}}}]

    # 表格行 → 文本
    if stripped.startswith("|") and stripped.endswith("|"):
        # 去除表头分隔行 (|---|---|)
        if re.match(r'^\|[-:| ]+\|$', stripped):
            return []
        # 提取单元格内容
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        content = "  |  ".join(c for c in cells if c)
        return [{"block_type": 2, "text": {"elements": [{"text_run": {"content": f"| {content} |"}}], "style": {}}}]

    # 普通文本
    return [{"block_type": 2, "text": {"elements": parse_inline(stripped), "style": {}}}]


def parse_inline(text):
    """解析内联格式（粗体、链接），返回 Feishu TextElement 列表"""
    elements = []
    pos = 0
    for m in re.finditer(r'\[([^\]]+)\]\(([^\)]+)\)|\*\*([^*]+)\*\*|\*([^*]+)\*', text):
        if m.start() > pos:
            elements.append({"text_run": {"content": text[pos:m.start()]}})
        if m.group(1):  # [text](url)
            elements.append({"link": {"content": m.group(1), "url": m.group(2)}})
        elif m.group(3):  # **bold**
            elements.append({"text_run": {"content": m.group(3), "bold": True}})
        elif m.group(4):  # *italic*
            elements.append({"text_run": {"content": m.group(4), "italic": True}})
        pos = m.end()
    if pos < len(text):
        elements.append({"text_run": {"content": text[pos:]}})
    return elements if elements else [{"text_run": {"content": text}}]


def push_to_feishu(markdown_content):
    """将报告推送到飞书文档"""
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        log("飞书 App 未配置，跳过")
        return None

    token = get_feishu_token()
    if not token:
        return None

    title = f"GitHub 项目周报 {TODAY}"
    doc_id = create_feishu_doc(token, title)
    if not doc_id:
        return None

    # 将 markdown 按行转为 blocks
    all_blocks = []
    for line in markdown_content.split("\n"):
        all_blocks.extend(md_line_to_feishu_blocks(line))

    # 每 25 个 block 一批写入（API 限制）
    batch_size = 25
    total_added = 0
    for i in range(0, len(all_blocks), batch_size):
        batch = all_blocks[i:i + batch_size]
        resp = feishu_request("POST", f"/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                            token=token, data={"children": batch})
        if resp.get("code") == 0:
            total_added += len(batch)
        else:
            log(f"飞书写入失败 (batch {i//batch_size}): {resp.get('msg','')}")

    doc_url = f"https://bytedance.feishu.cn/docx/{doc_id}"
    log(f"飞书推送完成，共 {total_added} 个内容块")

    # 群消息通知
    if FEISHU_WEBHOOK:
        try:
            card = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {"tag": "plain_text", "content": f"📊 GitHub 项目周报 ({TODAY})"},
                        "template": "indigo"
                    },
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": f"**报告已更新**\n📅 {TODAY}\n\n👉 [查看完整文档]({doc_url})"
                        },
                        {"tag": "hr"},
                        {"tag": "note", "elements": [{"tag": "plain_text", "content": "每日自动生成 · GitHub Actions"}]}
                    ]
                }
            }
            data = json.dumps(card).encode()
            req = urllib.request.Request(FEISHU_WEBHOOK, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
            log("群消息推送成功")
        except Exception as e:
            log(f"群消息推送失败: {e}")
    else:
        log("飞书 Webhook 未配置，跳过群消息")

    # 先获取文档的真实 file_token（通过 docx API 查文档信息）
    log("获取文档 file_token...")
    doc_info = subprocess.run(
        ["curl", "-s", "-X", "GET",
         f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}",
         "-H", f"Authorization: Bearer {token}",
         "-H", "Content-Type: application/json"],
        capture_output=True, text=True, timeout=15
    )
    log(f"文档信息: {doc_info.stdout[:400]}")
    try:
        doc_data = json.loads(doc_info.stdout)
        # 有些版本的 API 返回的 file_token 和 document_id 不同
        file_token = doc_data.get("data", {}).get("document", {}).get("document_id", doc_id)
    except:
        file_token = doc_id
    log(f"使用 file_token: {file_token}")

    # 用正确参数做 PATCH public（让文档公司内可编辑）
    log("--- PATCH public 公司内可编辑 ---")
    r = subprocess.run(
        ["curl", "-s", "-X", "PATCH",
         f"https://open.feishu.cn/open-apis/drive/v1/permissions/{file_token}/public?type=docx",
         "-H", f"Authorization: Bearer {token}",
         "-H", "Content-Type: application/json",
         "-d", '{"link_share_entity":"company_editable","security_entity":"anyone_can_view","external_access_entity":"open","invite_external":false}'],
        capture_output=True, text=True, timeout=15
    )
    log(f"PATCH public: {r.stdout[:500]}")
    
    # 也试不带 security_entity
    log("--- PATCH public 最小参数 ---")
    r = subprocess.run(
        ["curl", "-s", "-X", "PATCH",
         f"https://open.feishu.cn/open-apis/drive/v1/permissions/{file_token}/public?type=docx",
         "-H", f"Authorization: Bearer {token}",
         "-H", "Content-Type: application/json",
         "-d", '{"link_share_entity":"company_editable"}'],
        capture_output=True, text=True, timeout=15
    )
    log(f"PATCH public min: {r.stdout[:500]}")    return doc_url


# ═══ 主流程 ═══

def main():
    log(f"开始生成报告 ({TODAY})")

    all_time = api_get(f"{API_BASE}/search/repositories?q=stars:%3E100000&sort=stars&order=desc&per_page=15")
    new_week = api_get(f"{API_BASE}/search/repositories?q=created:%3E{WEEK_AGO}&sort=stars&order=desc&per_page=30")
    trending = fetch_trending()
    log(f"Trending 获取到 {len(trending)} 个仓库")

    content = build_report(all_time, new_week, trending)

    # 写入文件（给 GitHub 用）
    report_path = os.path.join(REPO_DIR, REPORT_FILE)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(content)
    log(f"报告写入: {REPORT_FILE}")

    # 推送到飞书文档
    doc_url = push_to_feishu(content)
    print(f"\n📄 飞书文档: {doc_url or '未创建'}")

    log("全部完成！")


if __name__ == "__main__":
    main()
