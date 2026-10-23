import os
import requests
import smtplib
import feedparser
from email.mime.text import MIMEText
from email.header import Header

def main():
    # 1. 读取环境变量
    api_key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    sender = os.environ.get('EMAIL_USER', '').strip()
    password = os.environ.get('EMAIL_PASS', '').strip()
    receiver = os.environ.get('TO_EMAIL', '').strip()

    # 2. 定义信息源（学术 + 科技媒体）
    urls = {
        'arXiv-CV': 'http://rss.arxiv.org/rss/cs.CV',
        'arXiv-GR': 'http://rss.arxiv.org/rss/cs.GR',
        'arXiv-NI': 'http://rss.arxiv.org/rss/cs.NI',
        'The Register': 'https://www.theregister.com/headlines.atom'
    }
    
    news_text = ''
    keywords_cv = ['pose', 'animation', 'motion', 'avatar', 'fomm', 'reconstruction', 'dance']
    keywords_net = ['routing', 'sdn', 'network', '5g', '6g', 'protocol', 'congestion', 'satellite', 'architecture']
    
    print("=== 开始抓取最新数据 ===")
    
    for name, url in urls.items():
        print(f"正在读取: {name} ...")
        try:
            feed = feedparser.parse(url)
            print(f"--> 从 {name} 成功解析到 {len(feed.entries)} 条原始数据。")
        except Exception as e:
            print(f"❌ 读取 {name} 失败: {e}")
            continue
            
        count = 0
        for entry in feed.entries:
            title = entry.title.lower()
            
            # 分支1：The Register (不过滤，直接取最新5篇)
            if name == 'The Register':
                news_text += f'[大厂八卦] {entry.title}\n'
                count += 1
            # 分支2：arXiv 网络论文
            elif name == 'arXiv-NI':
                if any(kw in title for kw in keywords_net):
                    news_text += f'[网络学术] {entry.title}\n'
                    count += 1
            # 分支3：arXiv 视觉/图形论文
            else:
                if any(kw in title for kw in keywords_cv):
                    news_text += f'[视觉动画] {entry.title}\n'
                    count += 1
                    
            # 每个源最多抓 5 篇，防止 token 爆炸
            if count >= 5:
                break

    if not news_text.strip():
        print('今天没有抓取到任何相关内容，跳过发送。')
        return
        
    print(f"=== 抓取完成！共获取 {len(news_text.splitlines())} 条资讯 ===")
    print(news_text) # 把这行打印出来，你在日志里就能看到到底抓了什么
    
    print("=== 开始请求 AI 总结 ===")

    # 3. 请求 AI
    headers = {
        'Authorization': f'Bearer {api_key}', 
        'Content-Type': 'application/json'
    }
    
    prompt = f'''你是一名学术研究助理，同时也是一名《计算机网络原理》教师。
以下是我今天抓取到的论文和科技新闻列表：
{news_text}

请严格执行以下指令，并直接输出最终的中文邮件正文：
1. 【视觉与动画精选】：从带有 [视觉动画] 标记的内容中，最多挑选 3 篇与姿态迁移、动画生成、FOMM 最相关的论文。为它们分别输出标题、研究方向和核心摘要。
- 标题（可保留英文）
   - 研究方向（如：基于扩散模型、大姿态变化等）
   - 核心摘要（用2-3句话提炼其创新点）
2. 【网络教学前沿】：从带有 [网络学术] 标记的内容中，挑选 2 篇，用中文概括其研究的网络问题（如路由、拥塞控制等），并设计一个适合本科生讨论的问题。
3. 【网管茶话会（趣味）】：从带有 [大厂八卦] 标记的内容中，挑选 2 篇最有趣、最贴近真实网络工程（比如断网事故、黑客攻击、大厂奇葩操作）的新闻，用中文讲个大概，并点出它与计算机网络原理（如 DNS、BGP、路由、安全、流媒体）的关联。
4. 如果某一部分今天没有抓取到内容，就跳过不写。排版要清晰易读，带好段落标题。'''
    
    data = {'model': 'deepseek-chat', 'messages': [{'role': 'user', 'content': prompt}]}
    res = requests.post('https://api.deepseek.com/v1/chat/completions', headers=headers, json=data)
    result = res.json()
    
    if 'choices' not in result:
        print('❌ AI 接口报错:', result)
        return
        
    content = result['choices'][0]['message']['content']
    print("=== AI 总结生成完毕，准备发送邮件 ===")

    # 4. 发送邮件
    msg = MIMEText(content, 'plain', 'utf-8')
    msg['Subject'] = Header('今日简报：FOMM精选 / 网络学术 / 科技茶话会', 'utf-8')
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
