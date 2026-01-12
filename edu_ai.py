import os
import smtplib
import feedparser
import urllib.parse
from datetime import datetime, timedelta
from time import mktime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from deep_translator import GoogleTranslator

def fetch_edu_news(days=7):
    # 核心机构与国家关键词
    orgs = '("College board" OR "Quest bridge" OR NACAC OR "Open doors" OR "Inside Higher Ed")'
    topics = '(AI OR "Artificial Intelligence" OR ChatGPT OR "Generative AI")'
    level = '("High School" OR "Secondary Education" OR "K12")'
    
    # 构建搜索词：机构+主题+高中阶段
    query = f"{orgs} {topics} {level}"
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    feed = feedparser.parse(rss_url)
    items = []
    threshold = datetime.now() - timedelta(days=days)
    
    for entry in feed.entries:
        if not hasattr(entry, 'published_parsed'): continue
        published_time = datetime.fromtimestamp(mktime(entry.published_parsed))
        if published_time > threshold:
            items.append({
                "title": entry.title,
                "url": entry.link,
                "source": entry.source.get('title', 'Education Media'),
                "date": published_time.strftime('%Y-%m-%d')
            })
        if len(items) >= 20: break
    return items

def send_email():
    sender = "alexanderxyh@gmail.com"
    password = os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com"]
    
    news_data = fetch_edu_news(days=7)
    if not news_data:
        print("本周暂无新的 AI 教育洞察。")
        return

    translator = GoogleTranslator(source='auto', target='zh-CN')
    rows = ""
    for item in news_data:
        try:
            chi_title = translator.translate(item['title'])
        except:
            chi_title = item['title']
        
        rows += f"""
        <tr>
            <td style="padding: 15px; border-bottom: 1px solid #e2e8f0;">
                <div style="font-size: 16px; font-weight: bold; color: #1e3a8a; margin-bottom: 5px;">{chi_title}</div>
                <div style="font-size: 12px; color: #64748b; margin-bottom: 8px;">{item['title']}</div>
                <div style="font-size: 11px; color: #94a3b8;">
                    <span style="background:#dbeafe; color:#1e40af; padding:2px 6px; border-radius:4px;">{item['source']}</span> | {item['date']} 
                    | <a href="{item['url']}" style="color:#2563eb; text-decoration:none;">阅读原文 →</a>
                </div>
            </td>
        </tr>"""

    html = f"""
    <html><body style="font-family: Arial; background:#f8fafc; padding:20px;">
        <div style="max-width: 650px; margin: 0 auto; background:#fff; border-radius:12px; border: 1px solid #e2e8f0; overflow:hidden;">
            <div style="background:#1e40af; padding:30px; text-align:center; color:#fff;">
                <h2 style="margin:0;">全球 AI 与教育观察</h2>
                <p style="opacity:0.8; font-size:14px; margin-top:10px;">Agent速递：全球7天AI与教育洞察</p>
            </div>
            <table style="width:100%; border-collapse:collapse;">{rows}</table>
        </div>
    </body></html>"""

    msg = MIMEMultipart()
    msg['Subject'] = "Agent速递：全球7天AI与教育洞察"
    msg['From'] = f"Alex Edu Intelligence <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.send_message(msg)
    print("✅ 教育报告已发送给两位老师。")

if __name__ == "__main__":
    send_email()
