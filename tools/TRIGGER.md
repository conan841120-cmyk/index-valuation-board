# 外部定时触发（解决 GitHub schedule 延迟）

## 为什么需要这个

GitHub Actions 的 `schedule` 触发器自 2026-08 起存在**平台级延迟**：

- 实测本项目连续两天延迟 **5h14m / 5h32m**（计划北京 08:30，实际 13:44 / 14:02 才跑）；
- 社区报告常见 **3–10 小时**，部分运行甚至**直接不触发**；
- 「避开整点/半点」（如改到 :17 / :43）**已被证伪**，并非高峰拥堵导致；
- 相比之下 `workflow_dispatch`（手动 / API 触发）**立即执行**。

因此本仓库保留两条 cron 作为兜底（见 `.github/workflows/daily.yml`）；若要「到点必跑」，用下面的外部定时器。

## 配方：cron-job.org（免费，无需信用卡）

### 第 1 步：建一个最小权限的 GitHub Token

1. 打开 <https://github.com/settings/personal-access-tokens/new>
2. **Token name**：`index-valuation-trigger`
3. **Expiration**：建议 1 年（到期重建）
4. **Repository access** → Only select repositories → 选 `conan841120-cmyk/index-valuation-board`
5. **Permissions** → Repository permissions → 只开 **Actions: Read and write**
6. Generate token 并复制（**只显示一次**；⚠️ 不要贴到任何聊天/对话里）

### 第 2 步：在 cron-job.org 建任务

1. 注册/登录 <https://cron-job.org>（免费）
2. Create cronjob，按下表填：

| 项 | 值 |
| --- | --- |
| Title | 指数估值看板每日触发 |
| URL | `https://api.github.com/repos/conan841120-cmyk/index-valuation-board/actions/workflows/daily.yml/dispatches` |
| Schedule | 每天 **08:30**，Timezone 选 **Asia/Shanghai** |
| Request method | **POST** |
| Header 1 | `Accept: application/vnd.github+json` |
| Header 2 | `Authorization: Bearer <第 1 步的 token>` |
| Header 3 | `X-GitHub-Api-Version: 2022-11-28` |
| Header 4 | `Content-Type: application/json` |
| Request body | `{"ref":"main"}` |

3. 保存后点 **TEST RUN**：返回 **204** 即成功；随后 Actions 页面会出现一次 `workflow_dispatch` 运行。

### 第 3 步：验证

```bash
gh run list --repo conan841120-cmyk/index-valuation-board --limit 5
```

应看到一次 `workflow_dispatch` 成功运行，时间 ≈ 你设定的点。

## 备选方案

- **Google Cloud Scheduler / Cloudflare Workers Cron**：同样 POST 上表的 URL + headers + body。
- **本机 launchd（不推荐）**：Mac 常睡眠/关机，不可靠；仅作补充，脚本见 `tools/trigger_dispatch.sh`。

## 备注

- Body 里的 `ref` 用默认分支 `main`。
- cron-job.org 免费版支持分钟级间隔、失败邮件通知。
- 若将来 GitHub 修好了 `schedule`，可以直接停掉外部任务（两条 cron 仍在兜底）。
