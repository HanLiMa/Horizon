# my_bot — 每日科技简报机器人

> 最后更新：**2026-10-30**

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
| 模块二 网络教学前沿 | `[网络前沿]` | arXiv-NI、IETF-RFC、APNIC-Blog、Cloudflare-Blog |
| 模块三 网管茶话会 | `[大厂八卦]` | The Register |

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

## 常见问题

**日志显示「某源返回 0 条」**
先分清是哪种：

- `arXiv-CV / GR / NI`：2026-10-30 实测 arXiv 的 RSS 服务端返回空 feed（连 `hep-th` 这种大板块也是 0 条），不是你的配置问题，等它恢复；或者改成 `export.arxiv.org/api/query` 接口抓取，那条路是通的。
- `The Register`：站点加了 JS 工作量证明反爬（返回「Are we human?」页面），`feedparser` 拿不到 XML。临时方案是换成 Ars Technica / Light Reading。
- 其余源：先在本地 `curl -I <url>` 确认地址还在，再检查是不是被限流（IEEE Xplore 偶发 418）。

**`❌ AI 接口报错`** — 多半是 Key 失效或额度用尽，返回体里会写明原因。

**`❌ 邮件发送失败`** — QQ 邮箱必须用授权码；确认 465 端口可用，以及 `EMAIL_PASS` 这个 secret 绑的是 `EMAIL_PASSWORD`。

**`找不到信息源配置文件: .../feeds.toml`** — `feeds.toml` 没提交进仓库，Actions 上拉不到。执行 `git add my_bot/feeds.toml`。

**`feeds.toml 里没有任何 enabled = true 的信息源`** — 所有源都被 `enabled = false` 关掉了。

## 变更记录

- **2026-10-30**：提示词抽到 `prompt.md`；信息源抽到 `feeds.toml`（新增 TOG / TPAMI / TVCG / NVIDIA / IETF-RFC / APNIC / Cloudflare）；`main.py` 改为配置驱动 + 跨源去重；workflow 的 Python 从 3.10 提到 3.11。
