import os
import requests
import smtplib
import feedparser
import markdown
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
    keywords_cv = ['pose', 'animation', 'motion', 'avatar', 'fomm', 'reconstruction', 
        'diffusion', 'gaussian', 'nerf', 'implicit', 'Image Generation', 'Image Animation', 'Pose Transfer', 'Video Generation']
    keywords_net = ['routing', 'sdn', 'network', '5g', '6g', 'protocol', 'congestion', 'satellite', 'architecture', 'wifi']
    
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
            
            # 提取时间、链接和摘要，并处理可能为空的情况
            pub_date = getattr(entry, 'published', '未知日期')
            pub_date = pub_date[:16] # 截取前16位字符，比如 "Fri, 24 Oct 2026"
            link = getattr(entry, 'link', '无链接')
            
            # 提取摘要并清理多余的 HTML 标签
            import re
            summary = getattr(entry, 'summary', '')
            summary = re.sub(r'<[^>]+>', '', summary).strip()
            summary = summary[:500] # 截取前300个字符，防止太长

            # 分支1：The Register
            if name == 'The Register':
                news_text += f'[大厂八卦] 日期:{pub_date} | 标题:{entry.title} | 链接:{link}\n摘要:{summary}\n'
                count += 1
                
            # 分支2：arXiv 网络论文
            elif name == 'arXiv-NI':
                if any(kw in title for kw in keywords_net):
                    news_text += f'[网络前沿] 日期:{pub_date} | 标题:{entry.title} | 链接:{link}\n摘要:{summary}\n'
                    count += 1
                    
            # 分支3：arXiv 视觉/图形论文
            else:
                if any(kw in title for kw in keywords_cv):
                    news_text += f'[视觉动画] 日期:{pub_date} | 标题:{entry.title} | 链接:{link}\n摘要:{summary}\n'
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
    
    prompt = f'''你是一名资深的计算机视觉研究助理，精通 First Order Motion Model (FOMM) 及其演进脉络。，同时也是一名《计算机网络原理》教师。
    以下是我今天抓取到的论文和科技新闻列表：
    {news_text}
    请严格执行以下指令，并直接输出最终的中文邮件正文：
    【视觉与动画精选】：【任务：FOMM 平行技术路线追踪】
    请列出 2-3 个与 FOMM 目标功能相同（驱动视频驱动源图像动画）但技术路线完全不同的代表性工作（注意：不要只找修补 FOMM 的论文，要找比如基于扩散模型的、基于 3D 高斯的、或者基于隐式形变的完全不同范式）。
    对于每一个工作，请输出：
        1. 【论文标题与年份】
        2. 【技术范式选择】：它采用了什么架构？
        3. 【为什么没走关键点路线】：它的设计动机是什么（例如是为了解决大姿态导致的局部扭曲，还是为了解决遮挡问题）？
        4. 【大姿态/遮挡表现】：它在 FOMM 容易失败的场景下表现如何（如果有量化数据请列出）？
    【网络教学前沿】：从带有 [网络学术] 标记的内容中，挑选 2 篇。对于每一个工作，请输出：
        1. 【标题与年份】
        2. 【研究问题与讨论设计】：用中文概括其研究的网络问题（如路由、拥塞控制等）
        3. 【讨论设计】：并设计一个适合本科生讨论的问题，并给出参考答案

    【网管茶话会（趣味）】：从带有 [大厂八卦] 标记的内容中，挑选 2 篇最有趣、最贴近真实网络工程（比如断网事故、黑客攻击、大厂奇葩操作）的新闻，对于每一个工作，请输出：
        1. 【标题与年份】
        2. 【内容概述】：用中文讲个大概，并点出它与计算机网络原理（如 DNS、BGP、路由、安全、流媒体）的关联。
        3. 【专家解读】：对于每个工作，请你扮演一个计算机网络的专家，用本科生能听懂的大白话给我讲：
            1）这到底是个什么技术/事故？
            2）如果是网络问题，它对应我《计算机网络原理》课本里的哪一章哪个知识点（比如 TCP 拥塞控制、BGP 路由、还是 DNS 劫持）？
            3）如果我在课堂上用它当案例，该怎么设计一个能让学生瞬间清醒的提问？”

    如果某一部分今天没有抓取到内容，就跳过不写。排版要清晰易读，带好段落标题。
    '''
    
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
