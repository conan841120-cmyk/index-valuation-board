# 外部定时触发备选（未启用）

本副本保留原有一条 `30 0 * * *` schedule（UTC；北京时间名义 08:30）。
定时触发可能延迟或未执行；不能据此保证准点启动或完成。
此文档仅说明备选办法，不代表已经配置第三方任务、Token 或实际触发过工作流。
外部服务也会排队、失败或延迟，`workflow_dispatch` 不提供准点保证。

## Token 与外部服务

如以后选择使用外部服务，可在 GitHub 的 fine-grained personal access token 设置中：

1. 只选择 `conan841120-cmyk/index-valuation-board` 这一个仓库。
2. 仓库权限仅授予 **Actions: Read and write**，不要授予源码写入等无关权限。
3. 设置尽可能短的有效期，例如 7–30 天，并安排到期轮换；用完或停止服务后撤销。
4. Token 由用户自行存入所选服务的受保护请求头配置，不要贴进聊天、源码或日志。

外部服务需要保存 Token 才能代为触发工作流，因此增加第三方存储及泄露风险。
配置前应确认服务对请求头、访问日志和账户的保护方式；本项目没有保存或新增任何秘密。

## 请求格式（仅供参考）

| 项 | 值 |
| --- | --- |
| URL | `https://api.github.com/repos/conan841120-cmyk/index-valuation-board/actions/workflows/daily.yml/dispatches` |
| Method | `POST` |
| Header | `Accept: application/vnd.github+json` |
| Header | `Authorization: Bearer <由用户自行配置的 token>` |
| Header | `X-GitHub-Api-Version: 2022-11-28` |
| Header | `Content-Type: application/json` |
| Body | `{"ref":"main"}` |

可选调度服务包括 cron-job.org、Google Cloud Scheduler 或 Cloudflare Workers Cron。
本机调度受睡眠和关机影响。上述方案目前均未启用，也不承诺到点必跑。

## 必须验证实际运行结果

HTTP **204 只表示 GitHub 接受了请求**，不代表工作流已经启动、构建完成或页面部署成功。
后续需要查看 Actions 对应 `workflow_dispatch` 运行，确认 build 和 deploy 均成功，再核对页面数据日期。
重复请求可能造成重复运行，不应仅凭 204 连续补触发。

本地修复验收使用 `python3 tools/verify_local.py`，不需要任何外部调度或 Token。
