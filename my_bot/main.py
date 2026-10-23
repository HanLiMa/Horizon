import os
import requests
import smtplib
import feedparser
from email.mime.text import MIMEText
from email.header import Header

def main():
    # 1. 读取环境变量 (GitHub Secrets 会自动注入)
    api_key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    sender = os.environ.get('EMAIL_USER', '').strip()
    password = os.environ.get('EMAIL_PASS', '').strip()
    receiver = os.environ.get('TO_EMAIL', '').strip()

    # 2. 定义信息源
    urls = {
        'arXiv-CV': 'http://rss.arxiv.org/rss/cs.CV',
        'arXiv-GR': 'http://rss.arxiv.org/rss/cs.GR',
        'The Register': 'https://www.theregister.com/headlines.atom'
    }
    
    news_text = ''
    # 针对 arXiv 的关键词过滤词库
    keywords = ['pose', 'animation', 'motion', 'avatar', 'fomm', 'reconstruction']
    
    print("开始抓取最新数据...")
    
    for name, url in urls.items():
        print(f"正在读取: {name}")
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"读取 {name} 失败: {e}")
            continue
            
        count = 0
        for entry in feed.entries:
            title = entry.title.lower()
            
            # 分支1：The Register (综合科技新闻，不严格过滤，取最新5条)
            if name == 'The Register':
                news_text += f'[The Register] {entry.title}\n'
                count += 1
            # 分支2：arXiv (学术论文，必须命中关键词)
            else:
                if any(kw in title for kw in keywords):
                    news_text += f'[{name}] {entry.title}\n'
                    count += 1
                    
            # 限制每个源最多抓取 5 篇，防止信息过载
            if count >= 5:
                break

    if not news_text.strip():
        print('今天没有抓取到任何相关内容，跳过发送。')
        return
        
    print(f"抓取完成！共获取 {len(news_text.splitlines())} 条资讯，开始请求 AI 总结...")

    # 3. 构造 Prompt 并请求 DeepSeek
    headers = {
        'Authorization': f'Bearer {api_key}', 
        'Content-Type': 'application/json'
    }
    
    prompt = f'''你是一名学术研究助理，同时也是一名计算机网络原理教师。
以下是我今天从不同源抓取到的论文和新闻列表：
{news_text}

请严格执行以下指令，并直接输出最终的中文邮件正文：
1. 【学术精选】：从带有 [arXiv-CV] 或 [arXiv-GR] 标记的内容中，最多挑选出 5 篇与姿态迁移、动画生成、FOMM 最相关的论文。为它们分别输出：
   - 标题（可保留英文）
   - 研究方向（如：基于扩散模型、大姿态变化等）
   - 核心摘要（用2-3句话提炼其创新点）
2. 【网络前沿】：从带有 [The Register] 标记的内容中，挑选 2 篇与网络技术、底层硬件或前沿科技最相关的新闻，用简短的英文/中文概括，并结合计算机网络原理，给出一个适合课堂讨论的问题。
3. 如果某一部分今天没有抓取到内容，就跳过不写。格式要清晰易读。'''
    
    data = {'model': 'deepseek-chat', 'messages': [{'role': 'user', 'content': prompt}]}
    res = requests.post('https://api.deepseek.com/v1/chat/completions', headers=headers, json=data)
    result = res.json()
    
    if 'choices' not in result:
        print('AI 接口报错:', result)
        return
        
    content = result['choices'][0]['message']['content']
    print("AI 总结生成完毕，准备发送邮件...")

    # 4. 发送邮件
    msg = MIMEText(content, 'plain', 'utf-8')
    msg['Subject'] = Header('今日精筛：FOMM与网络前沿简报', 'utf-8')
    msg['From'] = sender
    msg['To'] = receiver

    try:
        smtp = smtplib.SMTP_SSL('smtp.qq.com', 465)
        smtp.login(sender, password)
        smtp.sendmail(sender, [receiver], msg.as_string())
        smtp.quit()
        print('邮件发送成功！')
    except Exception as e:
        print(f'邮件发送失败: {e}')

if __name__ == "__main__":
    main()
