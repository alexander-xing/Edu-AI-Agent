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
    clean = "".join(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', title))
    return clean[:20].lower()

def is_garbage_news(title):
    """过滤人事变动、委任、辞职等无关信息"""
    garbage_keywords = [
        'board member', 'board of directors', 'appoints', 'appointment', 'resigns', 
        'joins', 'promotion', 'hiring', 'CEO', 'CFO', '人事', '任职', '董事会', '委任'
    ]
    title_lower = title.lower()
    return any(k in title_lower for k in garbage_keywords)

def fetch_edu_news(days=14):
    # --- 中国区关键词：聚焦四城一梯队名校及政策 ---
    # 领域1：四城名校动态
    china_schools = '(北京 OR 上海 OR 杭州 OR 深圳) (国际学校 OR 实验学校 OR 名校) (录取 OR 榜单 OR 升学 OR 改革 OR 动态 OR 校庆)'
    # 领域2：C9及来华留学
    china_c9 = '("C9高校" OR 清华 OR 北大 OR 复旦 OR 上海交大 OR 浙大) (来华留学 OR 留学生政策 OR 国际生招生)'
    # 领域3：国家层面趋势
    china_policy = '(教育部 OR 国家层面 OR 教育部办公厅) (政策 OR 减负 OR 数字化 OR 民办教育规范)'
    
    china_queries = [china_schools, china_c9, china_policy]

    # --- 国际区源：聚焦洞察与AI ---
    intl_sources = [
        'College Board', 'IBO', 'UCAS', 'Cambridge International', 
        'World Economic Forum Education', 'EdSurge AI', 'TechCrunch Education', 
        'UNESCO AI Education', 'MIT Technology Review Education'
    ]

    # 定义两个板块
    sections = {
        "policy": {"name": "升学政策与形势", "icon": "🎓", "color": "#1e3a8a", "keywords": ["policy", "admission", "visa", "sat", "ap", "ib", "enrollment", "升学", "招生", "政策", "榜单"]},
        "ai": {"name": "AI 与教学实践", "icon": "🤖", "color": "#4338ca", "keywords": ["ai", "chatgpt", "generative", "intelligence", "edtech", "人工智能", "数字化", "智慧课堂"]}
    }

    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    all_data = {k: {"china": [], "intl": []} for k in sections.keys()}
    seen_fingerprints = set()

    # 抓取中国动态
    for q in china_queries:
        encoded_q = urllib.parse.quote(q)
        url = f"https://news.google.com/rss/search?q={encoded_q}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold or is_garbage_news(entry.title): continue
            
            fingerprint = get_core_fingerprint(entry.title)
            if fingerprint in seen_fingerprints: continue

            # 自动分入两个板块
            title_lower = entry.title.lower()
            target_sec = None
            if any(k in title_lower for k in sections["ai"]["keywords"]): target_sec = "ai"
            elif any(k in title_lower for k in sections["policy"]["keywords"]): target_sec = "policy"
            
            if target_sec and len(all_data[target_sec]["china"]) < 10:
                seen_fingerprints.add(fingerprint)
                all_data[target_sec]["china"].append({
                    "chi": entry.title, "eng": "", "url": entry.link,
                    "source": entry.source.get('title', '中国教育动态'), "date": pub_time.strftime('%m-%d')
                })
        time.sleep(0.5)

    # 抓取国际视野
    for src in intl_sources:
        encoded_q = urllib.parse.quote(src)
        url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold or is_garbage_news(entry.title): continue

            fingerprint = get_core_fingerprint(entry.title)
            if fingerprint in seen_fingerprints: continue

            title_lower = entry.title.lower()
            target_sec = None
            if any(k in title_lower for k in sections["ai"]["keywords"]): target_sec = "ai"
            elif any(k in title_lower for k in sections["policy"]["keywords"]): target_sec = "policy"

            if target_sec and len(all_data[target_sec]["intl"]) < 10:
                seen_fingerprints.add(fingerprint)
                try:
                    chi_title = translator.translate(entry.title)
                except: chi_title = entry.title
                
                all_data[target_sec]["intl"].append({
                    "chi": chi_title, "eng": entry.title, "url": entry.link,
                    "source": entry.source.get('title', src), "date": pub_time.strftime('%m-%d')
                })
        time.sleep(0.3)

    return all_data, sections

def format_html(data, sections):
    rows = ""
    for sec_id, sec_info in sections.items():
        rows += f'<tr><td style="padding:15px; background:{sec_info["color"]}; color:#fff; font-weight:bold; font-size:16px;">{sec_info["icon"]} {sec_info["name"]}</td></tr>'
        for reg_id, reg_name in [("china", "📍 中国动态 (京沪杭深/C9/趋势)"), ("intl", "🌐 国际视野 (趋势/AI/洞察)")]:
            items = data[sec_id][reg_id]
            rows += f'<tr><td style="padding:8px 15px; background:#f1f5f9; font-weight:bold; color:#475569; font-size:12px; border-left:4px solid {sec_info["color"]};">{reg_name}</td></tr>'
            if not items:
                rows += '<tr><td style="padding:15px; color:#94a3b8; font-size:12px; background:#fff; text-align:center;">近期暂无高度相关动态</td></tr>'
            else:
                for item in items:
                    eng_html = f'<div style="font-size:11px; color:#64748b; margin-bottom:6px;">{item["eng"]}</div>' if item["eng"] else ""
                    rows += f"""
                    <tr><td style="padding:12px 15px; border-bottom:1px solid #e5e7eb; background:#fff;">
                        <div style="font-size:14px; font-weight:bold; color:#1e293b; margin-bottom:4px; line-height:1.4;">{item['chi']}</div>
                        {eng_html}
                        <div style="font-size:11px; color:#94a3b8;"><b>{item['source']}</b> | {item['date']} | <a href="{item['url']}" style="color:{sec_info['color']}; text-decoration:none; font-weight:bold;">原文详情 →</a></div>
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
                <h1 style="margin:0; font-size:22px;">教育情报 Agent 速递</h1>
                <p style="font-size:13px; margin-top:10px; opacity:0.9;">14天垂直观察：京沪杭深名校、C9政策、全球AI洞察</p>
                <div style="margin-top:12px; font-size:11px; background:rgba(255,255,255,0.2); display:inline-block; padding:4px 15px; border-radius:20px;">
                    已剔除人事变动，保留核心深度资讯
                </div>
            </div>
            <table style="width:100%; border-collapse:collapse;">{content}</table>
        </div></body></html>"""

    msg = MIMEMultipart()
    msg['Subject'] = f"教育情报 Agent: 14天垂直速递 ({datetime.now().strftime('%m/%d')})"
    msg['From'] = f"Alex Edu Intel <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, pw)
        server.send_message(msg)
    print(f"✅ 发送完毕。共计 {total} 条高价值新闻。")

if __name__ == "__main__":
    send_email()
