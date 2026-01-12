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
# 1. 核心配置与工具函数
# --------------------------------------------------------------------------------

def get_sim_hash(title):
    """提取标题特征指纹用于去重"""
    clean = "".join(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', title))
    return clean[:25].lower()

def is_garbage_news(title):
    """过滤人事变动、委任等非业务资讯"""
    garbage_keywords = [
        'board member', 'appoints', 'appointment', 'resigns', 'joins', 
        'promotion', 'hiring', 'CEO', 'CFO', 'VP', '人事', '任职', '董事会', '委任'
    ]
    title_lower = title.lower()
    return any(k in title_lower for k in garbage_keywords)

def fetch_edu_news(days=30):
    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    results = {"china": [], "intl": []}
    seen_fingerprints = set()

    # --- A. 20个特定的海外名校官方 RSS 频道 ---
    specific_uni_feeds = [
        "https://news.harvard.edu/gazette/feed/",
        "https://news.stanford.edu/feed/",
        "https://www.ox.ac.uk/news-rss-feed",
        "https://www.cam.ac.uk/news/feed",
        "https://web.mit.edu/news/rss/topic/education.xml",
        "https://news.yale.edu/topics/education/rss",
        "https://www.princeton.edu/news/rss",
        "https://www.upenn.edu/penn-news/rss",
        "https://www.cornell.edu/news/rss",
        "https://www.ucl.ac.uk/news/rss",
        "https://www.imperial.ac.uk/news/rss",
        "https://www.lse.ac.uk/News/RSS-Feeds",
        "https://news.berkeley.edu/feed/",
        "https://news.uchicago.edu/rss-feeds",
        "https://www.unimelb.edu.au/news/rss",
        "https://www.sydney.edu.au/news-opinion/rss.xml",
        "https://www.nyu.edu/about/news-publications/news/rss.xml",
        "https://www.nus.edu.sg/news/rss",
        "https://www.utoronto.ca/news/feed",
        "https://www.ethz.ch/en/news-and-events/eth-news/rss.xml"
    ]

    # --- B. 中国教育动态查询 (京沪杭深/C9/AI实践) ---
    china_queries = [
        '(北京 OR 上海 OR 深圳 OR 杭州) (国际学校 OR 名校) (录取 OR 招生 OR 升学榜单 OR 改革)',
        '(新浪教育 OR 顶思 OR 腾讯教育) (AI实践 OR 智慧教育 OR 教育数字化 OR 教授观点)',
        '("C9高校" OR 清华 OR 北大 OR 复旦 OR 浙大) (针对中国学生 OR 招生简章 OR 来华留学)'
    ]

    # --- C. 国际视野广域查询 (补充源) ---
    intl_queries = [
        '("Top 100 Universities" OR "Ivy League") (Admissions for Chinese students OR Visa OR Requirements)',
        '("EdSurge" OR "EdWeek") (AI classroom practice OR Generative AI Case Study OR Implementation)',
        '(Professor OR Scholar OR Dean) (Future of Education OR AI Trends OR Insight)'
    ]

    # 1. 抓取中国区动态 (限额 10 条)
    for q in china_queries:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold or is_garbage_news(entry.title): continue
            
            fp = get_sim_hash(entry.title)
            if fp not in seen_fingerprints and len(results["china"]) < 10:
                seen_fingerprints.add(fp)
                results["china"].append({
                    "title": entry.title,
                    "eng_title": "",
                    "source": entry.source.get('title', '中国教育源'),
                    "url": entry.link,
                    "date": pub_time.strftime('%m-%d')
                })
        time.sleep(0.5)

    # 2. 抓取特定名校 RSS 源 (限额 10 条优先填充)
    for feed_url in specific_uni_feeds:
        if len(results["intl"]) >= 10: break
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                pub_time = datetime.fromtimestamp(mktime(entry.published_parsed)) if hasattr(entry, 'published_parsed') else datetime.now()
                if pub_time < threshold or is_garbage_news(entry.title): continue
                
                fp = get_sim_hash(entry.title)
                if fp not in seen_fingerprints and len(results["intl"]) < 10:
                    seen_fingerprints.add(fp)
                    try: chi_title = translator.translate(entry.title)
                    except: chi_title = entry.title
                    results["intl"].append({
                        "title": chi_title,
                        "eng_title": entry.title,
                        "source": "名校官方频道",
                        "url": entry.link,
                        "date": pub_time.strftime('%m-%d')
                    })
        except: continue

    # 3. 抓取国际广域源 (若 RSS 未满 10 条则补足)
    if len(results["intl"]) < 10:
        for q in intl_queries:
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if not hasattr(entry, 'published_parsed'): continue
                pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
                if pub_time < threshold or is_garbage_news(entry.title): continue
                
                fp = get_sim_hash(entry.title)
                if fp not in seen_fingerprints and len(results["intl"]) < 10:
                    seen_fingerprints.add(fp)
                    try: chi_title = translator.translate(entry.title)
                    except: chi_title = entry.title
                    results["intl"].append({
                        "title": chi_title,
                        "eng_title": entry.title,
                        "source": entry.source.get('title', '全球教育视野'),
                        "url": entry.link,
                        "date": pub_time.strftime('%m-%d')
                    })
            time.sleep(1)

    return results

# --------------------------------------------------------------------------------
# 2. 邮件格式化与发送
# --------------------------------------------------------------------------------

def format_html(data):
    sections = [
        ("china", "🇨🇳 第一部分：中国教育洞察 (京沪杭深/C9/名校)", "#c02424"),
        ("intl", "🌐 第二部分：国外教育洞察 (TOP100名校/AI实践/专家观点)", "#1a365d")
    ]
    
    rows = ""
    for key, name, color in sections:
        rows += f'<tr><td style="padding:15px; background:{color}; color:#fff; font-size:16px; font-weight:bold;">{name}</td></tr>'
        if not data[key]:
            rows += '<tr><td style="padding:20px; text-align:center; color:#94a3b8; background:#fff;">本期暂无匹配的高价值深度动态</td></tr>'
        else:
            for i, item in enumerate(data[key], 1):
                eng_html = f'<div style="font-size:11px; color:#64748b; margin-top:4px;">{item["eng_title"]}</div>' if item["eng_title"] else ""
                rows += f"""
                <tr><td style="padding:15px; border-bottom:1px solid #e2e8f0; background:#fff;">
                    <div style="font-size:14px; font-weight:bold; color:#1e293b; line-height:1.4;">{i:02d} {item['title']}</div>
                    {eng_html}
                    <div style="font-size:11px; color:#94a3b8; margin-top:8px;">
                        <span>🏢 {item['source']}</span> | <span>📅 {item['date']}</span> | 
                        <a href="{item['url']}" style="color:{color}; text-decoration:none; font-weight:bold;">查看原文 →</a>
                    </div>
                </td></tr>
                """
    return rows

def send_email():
    sender = "alexanderxyh@gmail.com"
    pw = os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com"]
    
    news_data = fetch_edu_news(days=30)
    content_html = format_html(news_data)
    
    email_template = f"""
    <html><body style="font-family:'PingFang SC',Arial,sans-serif; background:#f1f5f9; padding:15px;">
        <div style="max-width:700px; margin:0 auto; background:#fff; border-radius:8px; overflow:hidden; border:1px solid #e2e8f0; box-shadow:0 4px 6px rgba(0,0,0,0.05);">
            <div style="background:#1e293b; padding:30px; text-align:center; color:#fff;">
                <h1 style="margin:0; font-size:22px;">Alex's Education Intelligence</h1>
                <p style="font-size:13px; opacity:0.8; margin-top:8px;">30天全球深度洞察：中国名校、海外名校、AI教育案例</p>
            </div>
            <table style="width:100%; border-collapse:collapse;">{content_html}</table>
            <div style="padding:20px; text-align:center; font-size:11px; color:#94a3b8; background:#f8fafc;">
                去重机制已开启 | 搜索跨度：30天 | 信号源：Top 50 中国源 & 20所全球名校官方RSS
            </div>
        </div>
    </body></html>
    """

    msg = MIMEMultipart()
    # 按照要求修改的主题
    msg['Subject'] = f"Ying大人的'垂直教育情报每日滚动刷新'：30天全球深度精华版 (10+10) ({datetime.now().strftime('%m/%d')})"
    msg['From'] = f"Edu Intelligence Agent <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(email_template, 'html'))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.send_message(msg)
        print(f"✅ 成功发送深度洞察报告。")
    except Exception as e:
        print(f"❌ 发送失败: {e}")

if __name__ == "__main__":
    send_email()
