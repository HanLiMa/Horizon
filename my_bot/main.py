import os
import requests
import smtplib
import feedparser
from email.mime.text import MIMEText
from email.header import Header

def main():
    # 1. 读取环境变量 (GitHub Secrets 会自动把它们注入进来)
    api_key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    sender = os.environ.get('EMAIL_USER', '').strip()
    password = os.environ.get('EMAIL_PASS', '').strip()
    receiver = os.environ.get('TO_EMAIL', '').strip()

    # 2. 抓取并粗筛
    urls = {
        'arXiv 机器视觉': 'http://rss.arxiv.org/rss/cs.CV',
        'arXiv 图形学': 'http://rss.arxiv.org/rss/cs.GR'
    }
    
    news_text = ''
    keywords = ['pose', 'animation', 'motion', 'avatar', 'fomm', 'reconstruction']
    
    for name, url in urls.items():
        feed = feedparser.parse(url)
        count = 0
        for entry in feed.entries:
            title = entry.title.lower()
            if any(kw in title for kw in keywords):
                news_text += f'- {entry.title}\n'
                count += 1
            if count >= 15:
                break

    if not news_text.strip():
        print('今天没有抓取到相关的新论文，跳过发送。')
        return

    # 3. 构造 Prompt 并请求 DeepSeek
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    prompt = f'''你是一名学术研究助理。这是我今天从 arXiv 抓取到的相关论文标题：
{news_text}

请严格执行以下指令：
1. 从中【最多】挑选出 5 篇与姿态迁移、动画生成、FOMM 最相关的论文。
2. 为这 5 篇论文分别输出：
   - 【论文标题】
   - 【研究方向】
   - 【核心摘要】
3. 如果今天相关的论文不足 5 篇，就有几篇写几篇。
4. 最后，单独给出一段针对《计算机网络原理》教师的教学建议。'''
    
    data = {'model': 'deepseek-chat', 'messages': [{'role': 'user', 'content': prompt}]}
    res = requests.post('https://api.deepseek.com/v1/chat/completions', headers=headers, json=data)
    result = res.json()
    
    if 'choices' not in result:
        print('AI 接口报错:', result)
        return
        
    content = result['choices'][0]['message']['content']

    # 4. 发送邮件
    msg = MIMEText(content, 'plain', 'utf-8')
    msg['Subject'] = Header('今日精筛：FOMM与动画生成简报', 'utf-8')
    msg['From'] = sender
    msg['To'] = receiver

    smtp = smtplib.SMTP_SSL('smtp.qq.com', 465)
    smtp.login(sender, password)
    smtp.sendmail(sender, [receiver], msg.as_string())
    smtp.quit()
    print('邮件发送成功！')

if __name__ == "__main__":
    main()
