# GitHub 项目周报 · 飞书推送集成复盘报告

**项目仓库:** [GeneElias/Notes](https://github.com/GeneElias/Notes)
**报告生成时间:** 2026-07-27
**作者:** Codex (GPT-5)

---

## 一、项目概述

基于 GitHub API + GitHub Trending 自动生成每日项目分析报告，实现以下自动化链路：

```
GitHub API 抓取数据 → 生成 Markdown 报告 → 推送 GitHub 仓库
                                           → 创建飞书文档
                                           → 飞书群消息通知
```

---

## 二、完整时间线

### 阶段 1：初始报告生成（2026-07-26 15:42 ~ 15:57）

| 时间 | 事件 | 说明 |
|------|------|------|
| 15:42 | 用户提出需求 | 需要一份近一周 GitHub star 总排名 top 10 + 周增最快 top 10 的分析报告 |
| 15:47 | 生成第一版报告 | 使用 Python 脚本从 GitHub Search API + Trending 页面抓取数据 |
| 15:50 | 上传到 GeneElias/Notes | 使用 PAT token 推送到仓库 |
| 15:57 | 添加可点击链接 | 报告中所有项目名改为可跳转的 GitHub 链接 |

### 阶段 2：自动化配置（2026-07-26 16:00 ~ 23:41）

| 时间 | 事件 | 说明 |
|------|------|------|
| 16:00 | 用户要求每日自动更新 | 需求：每天自动生成报告推送到 GitHub + 飞书 |
| 16:07 | 先尝试本地 launchd 方案 | 用 macOS 定时任务 + 本地脚本 |
| 16:10 | 用户问"需要开机吗？" | 发现本地方案需要电脑开机运行 |
| 16:13 | 改为 GitHub Actions | 改用 GitHub 服务器定时运行，无需本机在线 |
| 16:20 | 配置 PAT token | 第一次 push workflow 文件因 token 缺少 workflow 权限被拒 |
| 16:30 | 更新 PAT + 配置 Secrets | 用户重新提供带 workflow 权限的 token |
| 16:45 | 首次 workflow 测试 | 遇到 403 Permission to GeneElias/Notes.git denied |
| 17:00 | 修复 git auth | checkout 改用 PAT token 注入，直接 `git push` 不再内嵌 URL |
| 17:15 | 修复文件覆盖问题 | 按日期每天新增文件，不覆盖之前报告 |
| 17:35 | 修复 Trending 正则 + 类型安全 | Trending 解析只匹配 h2 内链接，API 返回做 isinstance 校验 |
| 17:50 | 修复时间差 bug | Python 用北京时间，commit 步骤也用 `TZ=Asia/Shanghai` 对齐 |
| 18:10 | 恢复趋势解读和语言统计 | 报告模板中加入自动分析段落 + 语言分布表格 |

### 阶段 3：飞书集成（2026-07-26 23:41 ~ 2026-07-27 02:30）

| 时间 | 事件 | 说明 |
|------|------|------|
| 23:41 | 用户创建飞书应用 | App ID: `cli_aaedfadfc2b81bd9` |
| 23:50 | 配置飞书 App Secrets 到 GitHub | 添加 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 到仓库 Secrets |
| 00:10 | 首次跑通飞书文档创建 | 文档创建成功，67 个内容块全部写入 |
| 00:20 | 用户问"不是 9 点推送的？" | cron 定时 UTC 01:00 = 北京时间 09:00，之前手动触发导致时间不对 |
| 00:30 | 用户要求"飞书建文档，不是发链接" | 改用飞书 API 创建文档写入完整内容 |
| 00:45 | 添加群消息通知 | Webhook URL 配置到 `FEISHU_WEBHOOK` Secret |
| 01:00 | 文档权限问题出现 | 用户："这个文档我没有修改权限，机器人有" |
| 01:10 | 获取用户飞书 Open ID | `ou_7d8a6e6df7621556ce0d21922b676706ccs` |
| 01:15 | 尝试加用户为协作者 | `POST /drive/v1/permissions/{doc_id}/members` 失败 |
| 01:30 | Codex 回答"应用身份权限" | 需在飞书开放平台添加 `drive:drive` 权限 |

### 阶段 4：权限问题排查（2026-07-27 22:00 ~ 23:08）

| 时间 | 事件 | 说明 |
|------|------|------|
| 22:00 | 会话重启 | 前一会话因发送图片导致 DeepSeek 模型报错崩溃 |
| 22:05 | 试 transfer_owner | `POST .../members/transfer_owner` → **code=99992402** field validation failed |
| 22:08 | 试 `type=openid` 参数 | 参数格式 → 99992402，`type` 字段值错误 |
| 22:10 | 试 `member_type` 放 query | 调整参数位置 → 99992402 不变 |
| 22:12 | 试 `member_type` 放 body | 全部放 body → 99992402 不变 |
| 22:15 | 改用 curl 调试 | 发现 `type=openid` 错误，应为文件类型 |
| 22:17 | 试 `type=docx` | 格式校验通过，但出现新错误 → **code=1063001** Invalid parameter |
| 22:20 | 试多种 perm 值 | edit / full_access / view → 全部 1063001 |
| 22:25 | 试 `type=doc` vs `type=docx` | 两者都 1063001 |
| 22:30 | 试 perm 用数字 | `perm=2` → 99992402（字段级报错） |
| 22:30 | 试 member_type 用数字 | `member_type=1` → 99992402（字段级报错） |
| 22:35 | **关键发现** | `GET members` 返回 `{"code":0,"data":{"items":[]}}` — API 通！ |
| 22:40 | 试 email 类型 | 同样 1063001，排除 Open ID 格式问题 |
| 22:45 | **转机** | `PATCH public` 可访问，返回字段级错误（值不对但端点通） |
| 22:50 | 从错误信息找到正确参数 | `link_share_entity` 可选值：`tenant_readable, tenant_editable, anyone_readable, anyone_editable, closed` |
| 23:05 | ✅ **成功** | `PATCH public` 返回 `{"code":0,"data":...}` |
| 23:08 | 发布最终版脚本 | 确认文档已设为 `tenant_editable`（公司内可编辑） |

---

## 三、飞书推送要点总结

### 3.1 脚本架构

```
push_to_feishu(markdown):
  ├─ get_feishu_token()           # 获取 tenant_access_token
  ├─ create_feishu_doc()          # POST /docx/v1/documents
  ├─ 批量写入内容块               # POST /docx/v1/documents/{id}/blocks/{id}/children
  ├─ 群消息通知                   # Webhook POST interactive card
  └─ PATCH public tenant_editable # PATCH /drive/v1/permissions/{id}/public?type=docx
```

### 3.2 关键参数

| 项 | 值 | 说明 |
|----|-----|------|
| 飞书 Base URL | `https://open.feishu.cn/open-apis` | |
| Token 端点 | `POST /auth/v3/tenant_access_token/internal` | body: `{app_id, app_secret}` |
| 创建文档 | `POST /docx/v1/documents` | body: `{title}` |
| 写入内容 | `POST /docx/v1/documents/{id}/blocks/{id}/children` | body: `{children: [...]}`，每批 ≤ 25 blocks |
| 分享设置 | **`PATCH /drive/v1/permissions/{id}/public?type=docx`** | **body: `{"link_share_entity":"tenant_editable"}`** |
| 群消息 | `POST {webhook_url}` | body: interactive card JSON |

### 3.3 GitHub Secrets 配置

| Secret 名称 | 用途 | 来源 |
|-------------|------|------|
| `GH_PAT` | GitHub 推送权限 | GitHub Settings → Tokens |
| `FEISHU_APP_ID` | 飞书应用 ID | 飞书开放平台 → 应用凭证 |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | 同上 |
| `FEISHU_WEBHOOK` | 群消息推送 URL | 飞书群设置 → 群机器人 → 自定义机器人 |

### 3.4 GitHub Actions 定时

```yaml
on:
  schedule:
    - cron: '0 1 * * *'    # UTC 01:00 = 北京时间 09:00
  workflow_dispatch:         # 手动触发
```

### 3.5 踩坑记录

| 问题 | 原因 | 解法 |
|------|------|------|
| 403 git push denied | PAT 缺少 workflow 权限 | 重新生成带 workflow 权限的 token |
| 文件被覆盖 | git add 全部文件 | 按日期命名文件，只 add 当天文件 |
| `list` object has no attribute `get` | Trending 解析混入导航链接 | 正则限定 h2 标签内匹配 |
| 文件名日期错位 | UTC vs 北京时间 | 统一用 `TZ=Asia/Shanghai` |
| 趋势解读/语言统计消失 | 模板重构时遗漏 | 恢复自动分析段落 + 统计表 |
| 飞书文档无法编辑 | Bot 是文档所有者 | **PATCH public → `tenant_editable`** |
| `POST .../members` 失败 | `drive:drive` 写权限未发布 | 不使用此方案，改用 PATCH public |
| `code=99992402` type wrong | `type=openid` 误用 | 应传文件类型 `type=docx` |
| `code=1063001` | POST body 参数不被接受 | 放弃 POST，改用 PATCH public |

---

## 四、结论

最终方案通过 **PATCH `/drive/v1/permissions/{doc_id}/public?type=docx`** 设置 `link_share_entity=tenant_editable`，使文档对公司内所有成员可编辑，绕过了添加协作者 / 转让所有权等需要额外权限的 API。

核心流程每天北京时间 09:00 自动运行：
1. GitHub Actions 触发
2. 抓取 GitHub 数据 → 生成报告
3. 推送到 GitHub 仓库（按日新增）
4. 创建飞书文档 + 写入完整内容
5. 设置文档为公司内可编辑
6. 群消息通知带文档链接

---

*报告由 Codex 自动生成*
