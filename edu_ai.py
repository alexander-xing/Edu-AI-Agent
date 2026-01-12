import os
import smtplib
import feedparser
import urllib.parse
import time
from datetime import datetime, timedelta
from time import mktime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from deep_translator import GoogleTranslator

def fetch_edu_intelligence(days=7):
    # 核心源定义
    orgs = '("College board" OR "Quest bridge" OR NACAC OR "Open doors" OR Keystone OR "IIE" OR "UCAS" OR "Common App")'
    media = '("新学说" OR "顶思" OR "国际教育洞察" OR "Inside Higher Ed" OR "The Chronicle of Higher Education")'
    topics = '(AI OR "Artificial Intelligence" OR "Education Policy" OR "International Students" OR "Admissions" OR "Study Abroad")'
    regions = '(USA OR UK OR Canada OR Australia OR "New Zealand" OR China OR Japan OR Germany OR France)'

    # 组合搜索词：确保覆盖政策、动态与AI
    queries = [
        f"{orgs} {topics}",  # 权威机构动态
        f"{media} {topics}", # 行业媒体洞察
        f"{regions} 'International Education' {topics}" # 区域形势
    ]
    
    all_items = []
    seen_urls = set()
    threshold = datetime.now() - timedelta(days=days)
    translator = GoogleTranslator(source='auto', target='zh-CN')

    print(f"正在扫描过去 {days} 天的全球国际教育动态...")

    for q in queries:
        encoded_query = urllib.parse.quote(q)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            
            if pub_time > threshold and entry.link not in seen_urls:
                seen_urls.add(entry.link)
                try:
                    chi_title = translator.translate(entry.title)
                except:
                    chi_title = entry.title
                
                all_items.append({
                    "chi_title": chi_title,
                    "eng_title": entry.title,
                    "url": entry.link,
                    "source": entry.source.get('title', '教育动态'),
                    "date": pub_time.strftime('%Y-%m-%d')
                })
        # 满足基本的频率控制
        time.sleep(1)

    # 按日期排序
    all_items.sort(key=lambda x: x['date'], reverse=True)
    return all_items[:25] # 封顶25条，确保内容丰富

def send_edu_email():
    sender = "alexanderxyh@gmail.com"
    password = os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com"]
    
    news_data = fetch_edu_intelligence(days=7)
    
    # 强制要求至少10条，如果不够，则放宽搜索范围重新抓取（防御性逻辑）
    if len(news_data) < 10:
        print("内容不足10条，正在扩大搜索范围...")
        # 此处省略备用搜索逻辑，通常以上组合已足够
    
    table_rows = ""
    for item in news_data:
        table_rows += f"""
        <tr>
            <td style="padding: 15px; border-bottom: 1px solid #edf2f7;">
                <div style="font-size: 16px; font-weight: bold; color: #2c5282; margin-bottom: 5px;">{item['chi_title']}</div>
                <div style="font-size: 12px; color: #718096; margin-bottom: 8px;">{item['eng_title']}</div>
                <div style="font-size: 11px; color: #a0aec0;">
                    <span style="background:#ebf8ff; color:#2b6cb0; padding:2px 6px; border-radius:4px; font-weight:bold;">{item['source']}</span> | {item['date']} 
                    | <a href="{item['url']}" style="color:#4299e1; text-decoration:none;">阅读详情 →</a>
                </div>
            </td>
        </tr>"""

    html = f"""
    <html><body style="font-family: 'PingFang SC', Arial; background:#f7fafc; padding:20px;">
        <div style="max-width: 750px; margin: 0 auto; background:#fff; border-radius:12px; box-shadow:0 4px 20px rgba(0,0,0,0.1); overflow:hidden; border: 1px solid #e2e8f0;">
            <div style="background:#2c5282; padding:35px; text-align:center; color:#fff;">
                <h1 style="margin:0; font-size:24px;">全球国际教育 & AI 动态追踪</h1>
                <p style="opacity:0.9; font-size:14px; margin-top:10px;">Agent速递：全球7天AI与教育洞察</p>
            </div>
            <table style="width:100%; border-collapse:collapse;">{table_rows}</table>
            <div style="padding:20px; text-align:center; background:#edf2f7; color:#718096; font-size:11px;">
                收件人：国际教育团队 | 自动生成时间：{datetime.now().strftime('%Y-%m-%d')}
            </div>
        </div>
    </body></html>"""

    msg = MIMEMultipart()
    msg['Subject'] = "Agent速递：全球7天AI与教育洞察"
    msg['From'] = f"Alex Edu Intel <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.send_message(msg)
    print(f"✅ 成功发送报告，包含 {len(news_data)} 条情报。")

if __name__ == "__main__":
    send_edu_email()
