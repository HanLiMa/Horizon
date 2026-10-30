import os
import re
import sys

try:
    import tomllib  # Python 3.11+ 标准库
except ModuleNotFoundError:  # 3.10 及更早没有，给个能看懂的提示
    sys.exit('需要 Python 3.11 或以上版本（读取 feeds.toml 依赖标准库 tomllib）。')

import requests
import smtplib
import feedparser
import markdown
from pathlib import Path
from email.mime.text import MIMEText
from email.header import Header

# 提示词模板文件，与 main.py 放在同一目录，改文案只需编辑这个文件，不用动代码
PROMPT_FILE = Path(__file__).with_name('prompt.md')
# 模板里用 {{news_text}} 占位，运行时替换成当天抓取的资讯
NEWS_PLACEHOLDER = '{{news_text}}'
# 信息源配置：增删信息源、改关键词只改这个文件
FEEDS_FILE = Path(__file__).with_name('feeds.toml')


def load_feeds():
    """读取 feeds.toml，返回启用的信息源列表（enabled = false 的自动跳过）。"""
    if not FEEDS_FILE.exists():
        raise FileNotFoundError(f'找不到信息源配置文件: {FEEDS_FILE}')

    with FEEDS_FILE.open('rb') as f:
        config = tomllib.load(f)

    feeds = [f for f in config.get('feeds', []) if f.get('enabled', True)]
    if not feeds:
        raise ValueError('feeds.toml 里没有任何 enabled = true 的信息源')
    print(f"已加载 {len(feeds)} 个信息源。")
    return feeds


def main():
    # 1. 读取环境变量
    api_key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    sender = os.environ.get('EMAIL_USER', '').strip()
    password = os.environ.get('EMAIL_PASS', '').strip()
    receiver = os.environ.get('TO_EMAIL', '').strip()

    # 2. 从 feeds.toml 读取信息源
    feeds = load_feeds()

    news_text = ''
    seen_links = set()
    total_items = 0

    print("=== 开始抓取最新数据 ===")

    for feed_cfg in feeds:
        name = feed_cfg.get('name', feed_cfg['url'])
        tag = feed_cfg.get('tag', '大厂八卦')
        keywords = [kw.lower() for kw in feed_cfg.get('keywords', [])]
        max_items = int(feed_cfg.get('max_items', 5))

        print(f"正在读取: {name} ...")
        try:
            feed = feedparser.parse(feed_cfg['url'])
        except Exception as e:
            print(f"❌ 读取 {name} 失败: {e}")
            continue

        print(f"--> 从 {name} 成功解析到 {len(feed.entries)} 条原始数据。")
        if not feed.entries:
            print(f"⚠️  {name} 返回 0 条：URL 可能失效，或被反爬拦截。")
            continue

        count = 0
        for entry in feed.entries:
            if count >= max_items:
                break

            title = getattr(entry, 'title', '')
            title_lower = title.lower()

            # 关键词过滤：keywords 为空表示不过滤，全收
            if keywords and not any(kw in title_lower for kw in keywords):
                continue

            link = getattr(entry, 'link', '无链接')
            # 去重：同一篇论文可能从多个源重复进来
            if link in seen_links:
                continue
            seen_links.add(link)

            # 提取时间、链接和摘要，并处理可能为空的情况
            pub_date = getattr(entry, 'published', '未知日期')
            pub_date = pub_date[:16]  # 截取前16位字符，比如 "Fri, 24 Oct 2026"

            # 提取摘要并清理多余的 HTML 标签
            summary = getattr(entry, 'summary', '')
            summary = re.sub(r'<[^>]+>', '', summary).strip()
            summary = summary[:500]  # 截取前500个字符，防止太长

            news_text += f'[{tag}] 日期:{pub_date} | 标题:{title} | 链接:{link}\n摘要:{summary}\n'
            count += 1
            total_items += 1

        print(f"--> {name} 命中 {count} 条。")

    if not news_text.strip():
        print('今天没有抓取到任何相关内容，跳过发送。')
        return
        
    print(f"=== 抓取完成！共获取 {total_items} 条资讯 ===")
    print(news_text) # 把这行打印出来，你在日志里就能看到到底抓了什么
    
    print("=== 开始请求 AI 总结 ===")

    # 3. 请求 AI
    headers = {
        'Authorization': f'Bearer {api_key}', 
        'Content-Type': 'application/json'
    }
    
    # 4. 读取提示词模板，把抓取到的资讯填进去
    template = PROMPT_FILE.read_text(encoding='utf-8')
    prompt = template.replace(NEWS_PLACEHOLDER, news_text)
    
    data = {'model': 'deepseek-chat', 'messages': [{'role': 'user', 'content': prompt}]}
    res = requests.post('https://api.deepseek.com/v1/chat/completions', headers=headers, json=data)
    result = res.json()
    
    if 'choices' not in result:
        print('❌ AI 接口报错:', result)
        return
        
    # AI 生成的是 Markdown 格式的纯文本
    content = result['choices'][0]['message']['content']
    
    # 将 Markdown 转换为 HTML，并加上一点简单的 CSS 样式让它更好看
    html_content = markdown.markdown(content)
    
    # 如果想加样式，可以包一层 div：
    html_content = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 15px; color: #333; line-height: 1.6;">
        {html_content}
    </div>
    """

    msg = MIMEText(html_content, 'html', 'utf-8') # 注意这里改成了 'html'
    msg['Subject'] = Header('今日精筛：FOMM与网络前沿简报', 'utf-8')
    msg['From'] = sender
    msg['To'] = receiver

    try:
        smtp = smtplib.SMTP_SSL('smtp.qq.com', 465)
        smtp.login(sender, password)
        smtp.sendmail(sender, [receiver], msg.as_string())
        smtp.quit()
        print('✅ 邮件发送成功！')
    except Exception as e:
        print(f'❌ 邮件发送失败: {e}')

if __name__ == "__main__":
    main()
