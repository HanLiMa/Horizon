# my_bot — 每日科技简报机器人

> 最后更新：**2026-11-03**

抓取 arXiv / 期刊 / 网络博客的最新内容，交给 DeepSeek 生成一份结构化中文简报，再用邮件发给自己。
定时任务跑在 GitHub Actions 上（[`daily_send.yml`](../.github/workflows/daily_send.yml)，每天 UTC 22:00 即北京时间 06:00）。

## 文件结构

| 文件 | 作用 | 什么时候改它 |
|---|---|---|
| `main.py` | 主流程：读配置 → 抓取 → 过滤 → 请求 AI → 发邮件 | 基本不用改 |
| `prompt.md` | 提示词模板，决定简报的模块划分和写作风格 | 想调整简报内容时改这里 |
| `feeds.toml` | 信息源清单（URL、分类标记、关键词、条数上限） | 想加/删信息源、改关键词时改这里 |

配置和提示词都独立成文件了，**日常维护不需要动 `main.py`**。

## 工作流程

```
feeds.toml ──> feedparser 抓取每个源
                     │
                     ▼
           按 keywords 过滤标题（空列表 = 不过滤）
                     │
                     ▼
           按 tag 打标记：[视觉动画] / [网络前沿] / [大厂八卦]
                     │
                     ▼
     拼进 prompt.md 的 {{news_text}} 占位符
                     │
                     ▼
       DeepSeek API（deepseek-chat）→ Markdown
                     │
                     ▼
       转 HTML + 套内联样式 → SMTP(smtp.qq.com:465) 发送
```

## 怎么改

### 1. 改简报内容 / 写作要求 → `prompt.md`

直接编辑正文即可。`{{news_text}}` 是唯一的占位符，运行时会被替换成当天抓到的资讯；其它大括号（比如你写 `{"key": 1}`）都不会被当作占位符，可以放心写。

三个模块分别对应三种标记，`prompt.md` 里提到的标记名要和 `feeds.toml` 的 `tag` 保持一致：

| 模块 | 标记 | 对应源 |
|---|---|---|
| 模块一 视觉与动画（FOMM 前沿） | `[视觉动画]` | arXiv-CV/GR、ACM-TOG、IEEE-TPAMI、IEEE-TVCG、NVIDIA-Blog |
| 模块二 网络教学前沿 | `[网络前沿]` | arXiv-NI、IETF-RFC、APNIC-Blog、Cloudflare-Blog、BlogGeek-WebRTC、WebRTC-Hacks |
| 模块三 网管茶话会 | `[大厂八卦]` | The Register |
| 模块四 省着用的视觉研究（算力与能耗视角） | `[视觉动画]` | 同模块一；今日无相关数据时由模型用已有知识补齐，并标注来源 |

### 2. 增删信息源 → `feeds.toml`

复制一段改改就行：

```toml
[[feeds]]
name = "Ars-Technica"                                     # 日志里显示的名字，随便起
url = "https://feeds.arstechnica.com/arstechnica/index"    # RSS / Atom 地址
tag = "大厂八卦"                                            # 只能是三个标记之一
keywords = []                                              # 空 = 不过滤，全收
max_items = 5                                              # 这一路最多收几条
enabled = true                                             # false = 临时停用，不用删配置
```

几点约定：

- `tag` 只有 `视觉动画` / `网络前沿` / `大厂八卦` 三个值有意义，写错的话 AI 那边就找不到对应模块的数据。
- `keywords` 是**标题**里的子串匹配（不区分大小写），任一命中即收录。
- 期刊 TOC 类源（TOG / TPAMI / TVCG）一期内容好几天不变，如果发现连续几天重复，可以把 `max_items` 调小，或者只保留一路期刊源。
- 同一链接只会收录一次（跨源自动去重）。
- 关键词是「标题子串」匹配，所以短词要留神：`rtc` 会把 `WebRTC` 一起收进来（通常是你想要的），`dash` 可能误吃 `dashboard`，`real-time` 比较宽泛。误伤多了就把它删掉。

### 流媒体 / 实时音视频

网络侧的三个学术/运维源（arXiv-NI、APNIC、Cloudflare）都加了一组流媒体关键词：`webrtc`、`rtp`、`srt`、`rtmp`、`hls`、`dash`、`cmaf`、`moq`、`media over quic`、`quic`、`http/3`、`low-latency`、`adaptive bitrate`、`jitter`、`congestion control`、`bbr`、`l4s`、`multicast`、`qoe`、`codec`、`av1`、`hevc`、`vvc`、`sub-second` 等。

但实测（2026-11-03）：这两个运维博客当前 30 条左右的标题里**没有一条命中流媒体词**，纯靠关键词几乎收不到 WebRTC 内容。所以另接了两个垂直源：

| 源 | 定位 |
|---|---|
| `BlogGeek-WebRTC`（bloggeek.me） | WebRTC 行业分析，作者 Tsahi Levent-Levi，圈内引用最多 |
| `WebRTC-Hacks`（webrtchacks.com） | 编解码、延迟、拥塞控制的工程实测与拆解 |

这两个站整站都是流媒体主题，`keywords = []` 不过滤，靠 `max_items = 3` 控量。

### 3. 本地测试

```bash
pip install requests feedparser markdown
export DEEPSEEK_API_KEY=sk-xxx EMAIL_USER=xxx@qq.com EMAIL_PASS=授权码 TO_EMAIL=xxx@qq.com
python my_bot/main.py
```

需要 **Python 3.11 或以上**（读 `feeds.toml` 依赖标准库 `tomllib`）。

## 环境变量

| 变量 | 含义 |
|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek 的 API Key |
| `EMAIL_USER` | 发件 QQ 邮箱地址 |
| `EMAIL_PASS` | QQ 邮箱的**授权码**（不是登录密码） |
| `TO_EMAIL` | 收件地址 |

在 GitHub 仓库的 Settings → Secrets and variables → Actions 里配置，名字要和 `daily_send.yml` 里的 `secrets.*` 对齐（注意 workflow 里 `EMAIL_PASS` 取的是名为 `EMAIL_PASSWORD` 的 secret）。

### arXiv 为什么有两套源

同一个分类抓两遍不是手抖，是两种通道各有各的问题：

| 通道 | 现状（2026-11-03 实测） | 角色 |
|---|---|---|
| **RSS**：`rss.arxiv.org/rss/cs.{CV,GR,NI}` | 服务端返回空 feed：892 字节、0 条 item，连 `cs.LG`、`hep-th` 这种大板块也是 0 条 | 兜底。arXiv 修好就自动恢复，留着不花钱 |
| **API**：`export.arxiv.org/api/query` | 可用，4 路各返回 10 条、命中 5 条，摘要完整（1200~1700 字符） | 主力。目前唯一能拿到「当天新论文」的通道 |

为什么不干脆只留 API：**API 会限流**。实测同一分钟内 `cs.CV` 查询返回 200，紧接着 `cs.NI` 就是 429 `Rate exceeded.`。单点依赖的话，你哪天看到「今天没有抓取到任何相关内容」，根本分不清是 arXiv 挂了还是被限流。

配置里的四条 API 源，查询式是写在 URL 里的，例如：

```
search_query=cat:cs.CV+AND+(abs:avatar+OR+abs:%22talking+head%22+OR+abs:portrait ...)
&sortBy=submittedDate&sortOrder=descending&max_results=10
```

含义是「在 cs.CV 分类里，摘要命中任一关键词的最新论文，取 10 条」。因为是服务端筛完才返回，这四路源的 `keywords` 必须留空 `[]`——否则会拿标题去二次过滤，把「摘要命中但标题没这个词」的论文全丢掉。

改查询式时注意三件事：

1. **URL 里不能有空格**，空格用 `+`，引号写成 `%22`，否则 `feedparser` 直接抛 `InvalidURL: URL can't contain control characters`。
2. **限流时不报错**：429 的响应体是 14 字节纯文本 `Rate exceeded.`，不是 XML，`feedparser` 只会安静地返回 0 条。所以 `main.py` 里判断的是 `feed.status`，不是「有没有解析出东西」。
3. **重试已内置**：对 `export.arxiv.org` 的请求失败（429/5xx）会等 3 秒重试，共 3 次——arXiv 官方要求请求间隔 ≥ 3 秒。

## 常见问题

**日志显示「某源返回 0 条」**
先分清是哪种：

- `arXiv-CV / GR / NI`（RSS）：服务端返回空 feed（连 `hep-th` 也是 0 条），不是你配置的问题，等它恢复；同时看 `arXiv-API-*` 那四路是否正常，正常情况下论文来自 API。
- `arXiv-API-*` 显示「重试后仍被限流（HTTP 429）」：arXiv 的限流是间歇性的，隔几分钟重跑即可；连续多天都限流，就把 `RETRY_DELAY` 调大或把 `max_results` 调小。
- `The Register`：站点加了 JS 工作量证明反爬（返回「Are we human?」页面），`feedparser` 拿不到 XML。临时方案是换成 Ars Technica / Light Reading。
- 其余源：先在本地 `curl -I <url>` 确认地址还在，再检查是不是被限流（IEEE Xplore 偶发 418）。

**`❌ AI 接口报错`** — 多半是 Key 失效或额度用尽，返回体里会写明原因。

**`❌ 邮件发送失败`** — QQ 邮箱必须用授权码；确认 465 端口可用，以及 `EMAIL_PASS` 这个 secret 绑的是 `EMAIL_PASSWORD`。

**`找不到信息源配置文件: .../feeds.toml`** — `feeds.toml` 没提交进仓库，Actions 上拉不到。执行 `git add my_bot/feeds.toml`。

**`feeds.toml 里没有任何 enabled = true 的信息源`** — 所有源都被 `enabled = false` 关掉了。

## 变更记录

- **2026-11-03**：新增 4 路 arXiv API 源（`arXiv-API-CV/GR/NI/MM`，服务端按分类+摘要检索）；`main.py` 增加限流退避重试与 `feed.status` 判读；arXiv RSS 地址改用 https（http 会 301）；`Meta-AI-Blog` 因原地址 404 换成 `Meta-Engineering-Blog`（engineering.fb.com）。同日另：网络侧源新增流媒体/实时音视频关键词组（WebRTC、RTP、HLS、DASH、MoQ、QUIC、低延迟、拥塞控制等）；新接 `BlogGeek-WebRTC` 与 `WebRTC-Hacks` 两个垂直源。
- **2026-10-30**：`prompt.md` 新增【模块四：省着用的视觉研究】，从算力/显存/能耗角度审视视觉与动画工作，含「一卡可做的动作」和「节能冷思考」；提示词抽到 `prompt.md`；信息源抽到 `feeds.toml`（新增 TOG / TPAMI / TVCG / NVIDIA / IETF-RFC / APNIC / Cloudflare）；`main.py` 改为配置驱动 + 跨源去重；workflow 的 Python 从 3.10 提到 3.11。
