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

def get_core_fingerprint(title):
    """提取语义指纹，用于去重"""
    clean = "".join(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', title))
    return clean[:25].lower()

def is_garbage_news(title):
    """过滤人事变动、会议简报、行政任命等低价值信息"""
    garbage_keywords = [
        'board member', 'board of directors', 'appoints', 'appointment', 'resigns', 
        'joins', 'promotion', 'hiring', 'CEO', 'CFO', 'VP', 'Executive', 'Senior', 
        '人事', '任职', '董事会', '委任', '提拔', '加盟', '任命'
    ]
    title_lower = title.lower()
    return any(k in title_lower for k in garbage_keywords)

def fetch_edu_news(days=14):
    # --- 中国区搜索（聚焦京沪杭深/C9/名校） ---
    china_queries = [
        '(北京 OR 上海 OR 杭州 OR 深圳) (国际学校 OR 名校) (录取 OR 榜单 OR 升学 OR 改革 OR 校庆)',
        '("C9高校" OR 清华 OR 北大 OR 复旦 OR 上海交大 OR 浙大) (来华留学 OR 留学生政策 OR 国际生招生)',
        '(教育部 OR 国家层面) (政策 OR 减负 OR 数字化 OR 民办教育规范)'
    ]

    # --- 国际视野分区搜索 ---
    # 分区1：前100大学升学政策与洞察
    intl_policy_query = '("Top 100 Universities" OR "Ivy League" OR "Russell Group" OR "College Board" OR "UCAS") (Admissions Policy OR SAT requirements OR Testing Policy OR Tuition OR Visa)'
    # 分区2：AI教学实践案例与观点
    intl_ai_query = '("K-12" OR "Higher Ed") (AI classroom practice OR Generative AI Case Study OR AI Education Policy OR AI Teaching Trends)'

    sections = {
        "policy": {"name": "升学政策与形势", "icon": "🎓", "color": "#1e3a8a", "keywords": ["policy", "admission", "visa", "sat", "ap", "ib", "enrollment", "升学", "招生", "政策", "榜单"]},
        "ai": {"name": "AI 与教学实践", "icon": "🤖", "color": "#4338ca", "keywords": ["ai", "chatgpt", "generative", "intelligence", "edtech", "人工智能", "数字化", "智慧课堂"]}
    }

    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    all_data = {k: {"china": [], "intl": []} for k in sections.keys()}
    seen_fingerprints = set()

    # 1. 抓取中国动态
    for q in china_queries:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold or is_garbage_news(entry.title): continue
            
            fingerprint = get_core_fingerprint(entry.title)
            if fingerprint in seen_fingerprints: continue

            title_lower = entry.title.lower()
            target_sec = "ai" if any(k in title_lower for k in sections["ai"]["keywords"]) else "policy"
            
            if len(all_data[target_sec]["china"]) < 10:
                seen_fingerprints.add(fingerprint)
                all_data[target_sec]["china"].append({
                    "chi": entry.title, "eng": "", "url": entry.link,
                    "source": entry.source.get('title', '中国教育动态'), "date": pub_time.strftime('%m-%d')
                })
        time.sleep(1)

    # 2. 抓取国际视野（分区精准抓取）
    for sec_id, q_str in [("policy", intl_policy_query), ("ai", intl_ai_query)]:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q_str)}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold or is_garbage_news(entry.title): continue

            fingerprint = get_core_fingerprint(entry.title)
            if fingerprint in seen_fingerprints: continue

            if len(all_data[sec_id]["intl"]) < 10:
                seen_fingerprints.add(fingerprint)
                try:
                    chi_title = translator.translate(entry.title)
                except: chi_title = entry.title
                
                all_data[sec_id]["intl"].append({
                    "chi": chi_title, "eng": entry.title, "url": entry.link,
                    "source": entry.source.get('title', '海外教育观察'), "date": pub_time.strftime('%m-%d')
                })
        time.sleep(1)

    return all_data, sections

def format_html(data, sections):
    rows = ""
    for sec_id, sec_info in sections.items():
        rows += f'<tr><td style="padding:15px; background:{sec_info["color"]}; color:#fff; font-weight:bold; font-size:16px;">{sec_info["icon"]} {sec_info["name"]}</td></tr>'
        for reg_id, reg_name in [("china", "📍 中国动态 (京沪杭深/C9/名校)"), ("intl", "🌐 国际视野 (名校政策/AI洞察)")]:
            items = data[sec_id][reg_id]
            rows += f'<tr><td style="padding:8px 15px; background:#f1f5f9; font-weight:bold; color:#475569; font-size:12px; border-left:4px solid {sec_info["color"]};">{reg_name}</td></tr>'
            if not items:
                rows += '<tr><td style="padding:15px; color:#94a3b8; font-size:12px; background:#fff; text-align:center;">暂无高度相关垂直资讯</td></tr>'
            else:
                for item in items:
                    eng_html = f'<div style="font-size:11px; color:#64748b; margin-bottom:6px;">{item["eng"]}</div>' if item["eng"] else ""
                    rows += f"""
                    <tr><td style="padding:12px 15px; border-bottom:1px solid #e5e7eb; background:#fff;">
                        <div style="font-size:14px; font-weight:bold; color:#1e293b; margin-bottom:4px; line-height:1.4;">{item['chi']}</div>
                        {eng_html}
                        <div style="font-size:11px; color:#94a3b8; display:flex; justify-content:space-between;">
                            <span><b>{item['source']}</b> | {item['date']}</span>
                            <a href="{item['url']}" style="color:{sec_info['color']}; text-decoration:none; font-weight:bold;">阅读原文 →</a>
                        </div>
                    </td></tr>"""
    return rows

def send_email():
    sender, pw = "alexanderxyh@gmail.com", os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com"]
    data, sections = fetch_edu_news(days=14)
    total = sum(len(v['china']) + len(v['intl']) for v in data.values())
    content = format_html(data, sections)
    
    html = f"""<html><body style="font-family:'PingFang SC',Arial,sans-serif; background:#f8fafc; padding:20px;">
        <div style="max-width:750px; margin:0 auto; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.1); border:1px solid #e2e8f0;">
            <div style="background:#1a365d; padding:35px; text-align:center; color:#fff;">
                <h1 style="margin:0; font-size:22px;">垂直教育情报 Agent</h1>
                <p style="font-size:13px; margin-top:10px; opacity:0.9;">14天洞察：名校升学政策与 AI 教学实践案例</p>
                <div style="margin-top:12px; font-size:11px; background:rgba(255,255,255,0.2); display:inline-block; padding:4px 15px; border-radius:20px;">
                    已自动过滤人事任免等杂讯 | 每分区限额 10 条
                </div>
            </div>
            <table style="width:100%; border-collapse:collapse;">{content}</table>
        </div></body></html>"""

    msg = MIMEMultipart()
    msg['Subject'] = f"垂直教育速递: 14天名校政策/AI实践案例 ({datetime.now().strftime('%m/%d')})"
    msg['From'] = f"Alex Edu Intel <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, pw)
        server.send_message(msg)
    print(f"✅ 发送完毕。共计 {total} 条高净值资讯。")

if __name__ == "__main__":
    send_email()
