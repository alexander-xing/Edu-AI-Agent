import os
import smtplib
import feedparser
import urllib.parse
import time
import re
from datetime import datetime, timedelta
from time import mktime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from deep_translator import GoogleTranslator

# --------------------------------------------------------------------------------
# 核心过滤与指纹函数
# --------------------------------------------------------------------------------

def get_sim_hash(title):
    clean = "".join(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', title))
    return clean[:30].lower()

def is_irrelevant(title):
    """过滤无价值的杂讯"""
    noise = ['board', 'appointment', 'appoints', 'hiring', 'CEO', 'CFO', '人事', '任职', '公告']
    return any(k in title.lower() for k in noise)

def fetch_edu_news(days=14):
    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    results = {"china": [], "intl": []}
    seen_fingerprints = set()

    # --- 第一部分：中国教育洞察 (精准源模式) ---
    china_queries = [
        # 1. 四城名校动态
        '(北京 OR 上海 OR 深圳 OR 杭州) (国际学校 OR 高中) (招生 OR 录取 OR 升学榜单)',
        # 2. 门户垂直频道+政策
        'site:edu.sina.com.cn OR site:edu.163.com (教育政策 OR 升学改革 OR 国际课程)',
        # 3. AI实践
        '(智慧校园 OR AI教育 OR 数字化) (实践案例 OR 落地 OR 试点)'
    ]

    # --- 第二部分：国外教育洞察 (全球Top100/权威媒体模式) ---
    intl_queries = [
        # 1. 名校针对中国学生的招生政策
        '(site:edu OR "Top 100 University") (Admissions OR Requirements) (Chinese students OR China)',
        # 2. AI教育实践 (锁定专业教育媒体)
        '(site:edsurge.com OR site:edweek.org OR site:bbc.co.uk/news/education) (AI classroom OR Generative AI Practice)',
        # 3. 专家洞察 (锁定学术领袖词汇)
        '(Professor OR Scholar OR Dean) (Future of Education OR AI Trends OR Insight)'
    ]

    # 抓取逻辑：中国
    for q in china_queries:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold or is_irrelevant(entry.title): continue
            
            fp = get_sim_hash(entry.title)
            if fp not in seen_fingerprints and len(results["china"]) < 15:
                seen_fingerprints.add(fp)
                results["china"].append({
                    "title": entry.title, "eng_title": "", "source": entry.source.get('title', '中国权威源'),
                    "url": entry.link, "date": pub_time.strftime('%m-%d')
                })

    # 抓取逻辑：国外
    for q in intl_queries:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold or is_irrelevant(entry.title): continue
            
            fp = get_sim_hash(entry.title)
            if fp not in seen_fingerprints and len(results["intl"]) < 15:
                seen_fingerprints.add(fp)
                try: chi_title = translator.translate(entry.title)
                except: chi_title = entry.title
                results["intl"].append({
                    "title": chi_title, "eng_title": entry.title, "source": entry.source.get('title', '海外名校/媒体'),
                    "url": entry.link, "date": pub_time.strftime('%m-%d')
                })
        time.sleep(1)

    return results

def format_html(data):
    sections = [
        ("china", "🇨🇳 第一部分：中国教育洞察 (名校动态/AI实践/政策)", "#c02424"),
        ("intl", "🌐 第二部分：国外教育洞察 (名校政策/AI案例/专家洞察)", "#1a365d")
    ]
    rows = ""
    for key, name, color in sections:
        rows += f'<tr><td style="padding:15px; background:{color}; color:#fff; font-size:16px; font-weight:bold;">{name}</td></tr>'
        items = data[key]
        if len(items) < 5:
            rows += '<tr><td style="padding:20px; text-align:center; color:#94a3b8; background:#fff;">正在深度挖掘更多高价值资讯... (当前匹配不足5条)</td></tr>'
        
        for i, item in enumerate(items, 1):
            eng_html = f'<div style="font-size:11px; color:#64748b; margin-top:4px;">{item["eng_title"]}</div>' if item["eng_title"] else ""
            rows += f"""
            <tr><td style="padding:15px; border-bottom:1px solid #e2e8f0; background:#fff;">
                <div style="font-size:14px; font-weight:bold; color:#1e293b; line-height:1.4;">{i:02d} {item['title']}</div>
                {eng_html}
                <div style="font-size:11px; color:#94a3b8; margin-top:8px;">
                    <span>🏢 {item['source']}</span> | <span>📅 {item['date']}</span> | 
                    <a href="{item['url']}" style="color:{color}; text-decoration:none; font-weight:bold;">阅读全文 →</a>
                </div>
            </td></tr>"""
    return rows

def send_email():
    sender, pw = "alexanderxyh@gmail.com", os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com"]
    
    news_data = fetch_edu_news(days=14)
    content_html = format_html(news_data)
    
    email_body = f"""
    <html><body style="font-family:'PingFang SC',Arial,sans-serif; background:#f1f5f9; padding:15px;">
        <div style="max-width:700px; margin:0 auto; background:#fff; border-radius:8px; overflow:hidden; border:1px solid #e2e8f0;">
            <div style="background:#1e293b; padding:30px; text-align:center; color:#fff;">
                <h1 style="margin:0; font-size:20px;">Ying大人的"垂直教育情报每日滚动刷新"</h1>
                <p style="font-size:13px; opacity:0.8; margin-top:8px;">14天精华版：Top 100 大学 & 四城名校深度追踪</p>
            </div>
            <table style="width:100%; border-collapse:collapse;">{content_html}</table>
        </div>
    </body></html>"""

    msg = MIMEMultipart()
    msg['Subject'] = f"Ying大人的'垂直教育情报每日滚动刷新'：14天全球深度精华版 ({datetime.now().strftime('%m/%d')})"
    msg['From'] = f"Edu Intelligence Agent <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(email_body, 'html'))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, pw)
        server.send_message(msg)
    print("✅ 深度重构版邮件发送成功。")

if __name__ == "__main__":
    send_email()
