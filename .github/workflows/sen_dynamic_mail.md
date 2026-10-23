name: Dynamic AI Digest

on:
  schedule:
    - cron: '0 23 * * *' # 每天北京时间早上 7 点
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Send Dynamic Email directly
        env:
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
          EMAIL_USER: ${{ secrets.EMAIL_USER }}
          EMAIL_PASS: ${{ secrets.EMAIL_PASSWORD }}
          TO_EMAIL: ${{ secrets.TO_EMAIL }}
        run: |
          pip install requests feedparser
          python -c "
          import os, requests, smtplib, feedparser
          from email.mime.text import MIMEText
          from email.header import Header

          api_key = os.environ['DEEPSEEK_API_KEY'].strip()
          sender = os.environ['EMAIL_USER'].strip()
          password = os.environ['EMAIL_PASS'].strip()
          receiver = os.environ['TO_EMAIL'].strip()

          # 1. 抓取 arXiv 最新动态 (cs.CV 计算机视觉, cs.GR 图形学, cs.NI 网络)
          urls = {
              'cs.CV (机器视觉/姿态迁移)': 'http://rss.arxiv.org/rss/cs.CV',
              'cs.GR (图形学/动画)': 'http://rss.arxiv.org/rss/cs.GR',
              'cs.NI (网络前沿)': 'http://rss.arxiv.org/rss/cs.NI'
          }
          
          news_text = ''
          for name, url in urls.items():
              news_text += f'--- {name} ---\n'
              feed = feedparser.parse(url)
              # 每个分类取最新的 5 篇论文标题
              for entry in feed.entries[:5]:
                  news_text += f'- {entry.title}\n'

          # 2. 构造提示词，喂给 AI
          headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
          prompt = f'''你是一名学术研究助理和计算机网络原理教师。
          这是今天 arXiv 更新的最新论文列表：
          {news_text}
          
          请根据以上数据，分别输出以下两个任务：
          任务一：从中挑选与 First Order Motion Model (FOMM)、姿态迁移、动画生成相关的论文，简述其研究趋势。
          任务二：从中挑选与计算机网络相关的论文，提炼一个适合课堂讲解的知识点，并给出1个课堂讨论问题。'''
          
          data = {'model': 'deepseek-chat', 'messages': [{'role': 'user', 'content': prompt}]}
          res = requests.post('https://api.deepseek.com/v1/chat/completions', headers=headers, json=data)
          result = res.json()
          
          if 'choices' not in result:
              print('AI 接口报错:', result)
              exit(1)
              
          content = result['choices'][0]['message']['content']

          # 3. 发送邮件
          msg = MIMEText(content, 'plain', 'utf-8')
          msg['Subject'] = Header('你的专属动态 AI 简报', 'utf-8')
          msg['From'] = sender
          msg['To'] = receiver

          smtp = smtplib.SMTP_SSL('smtp.qq.com', 465)
          smtp.login(sender, password)
          smtp.sendmail(sender, [receiver], msg.as_string())
          smtp.quit()
          print('动态简报发送成功！')
          "
