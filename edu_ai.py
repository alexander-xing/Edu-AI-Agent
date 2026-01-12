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
# 1. 核心过滤与去重逻辑
# --------------------------------------------------------------------------------

def get_sim_hash(title):
    clean = "".join(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', title))
    return clean[:30].lower()

def is_garbage(title):
    """过滤人事任命、基建招标等低价值杂讯"""
    noise = ['appoints', 'resigns', 'hiring', 'CEO', 'CFO', '人事', '任职', '董事会', '委任', '招标']
    return any(k in title.lower() for k in noise)

def fetch_edu_news(days=14):
    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    results = {"china": [], "intl": []}
    seen_fingerprints = set()

    # --- 第一部分：中国教育洞察 (核心关键词锁定) ---
    china_queries = [
        # 1. 四城名校 & C9 动态
        '(北京 OR 上海 OR 深圳 OR 杭州) (国际学校 OR 高中 OR 清华 OR 北大) (招生 OR 录取 OR 升学)',
        # 2. 政策与AI实践
        '(教育部 OR 新浪教育 OR 顶思) (教育政策 OR AI教学 OR 数字化转型 OR 智慧课堂)'
    ]

    # --- 第二部分：国外教育洞察 (三位一体抓取) ---
    intl_queries = [
        # 维度 A：名校针对中国学生的招生政策
        '(site:edu OR "Top 100") (Admissions OR Requirements) (China OR Chinese students)',
        # 维度 B：AI教育实践 (Use Cases)
        '(site:edsurge.com OR site:timeshighereducation.com) (Generative AI OR ChatGPT) (Use Case OR Practice)',
        # 维度 C：教授学者洞察 (Trends)
        '(Professor OR Scholar OR Dean) (Future of Higher Education OR Trends OR Insight)'
    ]

    # 抓取逻辑：中国
    for q in china_queries:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold or is_garbage(entry.title): continue
            
            fp = get_sim_hash(entry.title)
            if fp not in seen_fingerprints and len(results["china"]) < 15:
                seen_fingerprints.add(fp)
                results["china"].append({
                    "title": entry.title, "eng_title": "", "source": entry.source.get('title', '中国核心教育源'),
                    "url": entry.link, "date": pub_time.strftime('%m-%d')
                })

    # 抓取逻辑：海外 (名校+AI实践+学者洞察)
    for q in intl_queries:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold or is_garbage(entry.title): continue
            
            fp = get_sim_hash(entry.title)
            if fp not in seen_fingerprints and len(results["intl"]) < 15:
                seen_fingerprints.add(fp)
                # 翻译标题
                try: chi_title = translator.translate(entry.title)
                except: chi_title = entry.title
                results["intl"].append({
                    "title": chi_title, "eng_title": entry.title, "source": entry.source.get('title', '海外权威源'),
                    "url": entry.link, "date": pub_time.strftime('%m-%d')
                })
        time.sleep(1) # 礼貌延迟

    return results

def format_html(data):
    sections = [
        ("china", "🇨🇳 第一部分：中国教育洞察 (名校录取/AI实践/政策)", "#c02424"),
        ("intl", "🌐 第二部分：国外教育洞察 (招生政策/AI案例/专家趋势)", "#1a365d")
    ]
    rows = ""
    for key, name, color in sections:
        rows += f'<tr><td style="padding:15px; background:{color}; color:#fff; font-size:16px; font-weight:bold;">{name}</td></tr>'
        items = data[key]
        if len(items) < 5:
            rows += '<tr><td style="padding:20px; text-align:center; color:#94a3b8; background:#fff;">深度挖掘中... 当前匹配不足5条高价值资讯</td></tr>'
        else:
            for i, item in enumerate(items, 1):
                eng_html = f'<div style="font-size:11px; color:#64748b; margin-top:4px;">{item["eng_title"]}</div>' if item["eng_title"] else ""
                rows += f"""
                <tr><td style="padding:15px; border-bottom:1px solid #e2e8f0; background:#fff;">
                    <div style="font-size:14px; font-weight:bold; color:#1e293b; line-height:1.4;">{i:02d} {item['title']}</div>
                    {eng_html}
                    <div style="font-size:11px; color:#94a3b8; margin-top:8px;">
                        <span>🏢 {item['source']}</span> | <span>📅 {item['date']}</span> | 
                        <a href="{item['url']}" style="color:{color}; text-decoration:none; font-weight:bold;">查看详情 →</a>
                    </div>
                </td></tr>"""
    return rows

def send_email():
    sender, pw = "alexanderxyh@gmail.com", os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com"]
    
    news_data = fetch_edu_news(days=14)
    content_html = format_html(news_data)
    
    email_body = f"""
    <html><body style="font-family:'PingFang SC',sans-serif; background:#f1f5f9; padding:15px;">
        <div style="max-width:700px; margin:0 auto; background:#fff; border-radius:8px; border:1px solid #e2e8f0; overflow:hidden;">
            <div style="background:#1e293b; padding:30px; text-align:center; color:#fff;">
                <h1 style="margin:0; font-size:22px;">Ying大人的"垂直教育情报每日滚动刷新"</h1>
                <p style="font-size:13px; opacity:0.8; margin-top:8px;">14天精华版：全球Top 100大学 & AI教育前瞻</p>
            </div>
            <table style="width:100%; border-collapse:collapse;">{content_html}</table>
            <div style="padding:15px; background:#f8fafc; font-size:11px; color:#94a3b8; text-align:center;">
                自动去重已开启 | 信号源：20+名校官方 & THE/EdSurge | 检索跨度：14天
            </div>
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
    print("✅ 重构版报告已成功推送到 Ying 达人的邮箱。")

if __name__ == "__main__":
    send_email()
