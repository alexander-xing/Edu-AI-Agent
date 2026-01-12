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
    return clean[:18].lower()

def fetch_edu_news(days=14):
    # 领域 1：国际学校（名校+趋势）
    q_intl_school = '(包玉刚 OR 平和双语 OR 世外 OR 鼎石 OR 贝赛思 OR 德威 OR 惠灵顿 OR "国际学校") (录取 OR 升学 OR 改革 OR 政策 OR 趋势)'
    # 领域 2：C9 高校与来华留学
    q_c9_study = '("C9联盟" OR 清华 OR 北大 OR 复旦 OR 交大 OR 浙大) (留学生政策 OR 招收国际生 OR 来华留学)'
    # 领域 3：中国教育最新趋势
    q_china_trend = '("中国教育" OR "民办教育" OR "中外办学" OR "智慧教育") (趋势 OR 报告 OR 政策 OR 数字化)'

    china_queries = [
        {"id": "intl_school", "q": q_intl_school},
        {"id": "c9", "q": q_c9_study},
        {"id": "trend", "q": q_china_trend}
    ]

    intl_sources = ['"College Board"', 'NACAC', 'UCAS', 'IBO', '"Cambridge International"', '"Education Week"', 'EdSurge']

    sections = {
        "policy": {"name": "升学、政策与形势", "icon": "🎓", "color": "#1e3a8a", "keywords": ["policy", "admissions", "visa", "sat", "ap", "ib", "ucas", "升学", "招生", "录取", "政策", "改革"]},
        "ai": {"name": "AI 与教学实践", "icon": "🤖", "color": "#4338ca", "keywords": ["ai", "chatgpt", "intelligence", "technology", "edtech", "人工智能", "数字化", "智慧教育"]},
        "market": {"name": "区域动态与行业洞察", "icon": "🌏", "color": "#0369a1", "keywords": ["trend", "market", "insight", "report", "趋势", "动态", "分析", "报告", "洞察"]}
    }

    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    all_data = {k: {"china": [], "intl": []} for k in sections.keys()}
    seen_fingerprints = set()

    # --- 强化版中国区抓取 ---
    print("正在深度检索中国教育动态...")
    for item in china_queries:
        encoded_q = urllib.parse.quote(item['q'])
        # 强制使用中文索引和中国区地理标识
        rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold: continue
            
            fingerprint = get_core_fingerprint(entry.title)
            if fingerprint in seen_fingerprints: continue

            # 自动分配板块
            title_lower = entry.title.lower()
            target_sec = "market"
            if any(k in title_lower for k in sections["policy"]["keywords"]): target_sec = "policy"
            elif any(k in title_lower for k in sections["ai"]["keywords"]): target_sec = "ai"

            if len(all_data[target_sec]["china"]) < 10:
                seen_fingerprints.add(fingerprint)
                all_data[target_sec]["china"].append({
                    "chi": entry.title, "eng": "", "url": entry.link,
                    "source": entry.source.get('title', '中国教育源'), "date": pub_time.strftime('%m-%d')
                })
        time.sleep(1)

    # --- 国际区抓取 ---
    print("正在检索国际教育视野...")
    for src in intl_sources:
        encoded_q = urllib.parse.quote(src)
        rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold: continue
            
            fingerprint = get_core_fingerprint(entry.title)
            if fingerprint in seen_fingerprints: continue

            title_lower = entry.title.lower()
            target_sec = "market"
            if any(k in title_lower for k in sections["policy"]["keywords"]): target_sec = "policy"
            elif any(k in title_lower for k in sections["ai"]["keywords"]): target_sec = "ai"

            if len(all_data[target_sec]["intl"]) < 10:
                seen_fingerprints.add(fingerprint)
                try:
                    chi_title = translator.translate(entry.title)
                except: chi_title = entry.title
                
                all_data[target_sec]["intl"].append({
                    "chi": chi_title, "eng": entry.title, "url": entry.link,
                    "source": entry.source.get('title', src), "date": pub_time.strftime('%m-%d')
                })
        time.sleep(0.5)

    return all_data, sections

def format_html(data, sections):
    rows = ""
    for sec_id, sec_info in sections.items():
        rows += f'<tr><td style="padding:15px; background:{sec_info["color"]}; color:#fff; font-weight:bold; font-size:16px; border-radius:4px 4px 0 0;">{sec_info["icon"]} {sec_info["name"]}</td></tr>'
        for reg_id, reg_name in [("china", "📍 中国动态 (垂直定制)"), ("intl", "🌐 国际视野 (14天热点)")]:
            items = data[sec_id][reg_id]
            rows += f'<tr><td style="padding:8px 15px; background:#f1f5f9; font-weight:bold; color:#475569; font-size:12px; border-left:4px solid {sec_info["color"]};">{reg_name}</td></tr>'
            if not items:
                rows += '<tr><td style="padding:15px; color:#94a3b8; font-size:12px; background:#fff; text-align:center;">暂无匹配的高质量深度动态</td></tr>'
            else:
                for item in items:
                    eng_html = f'<div style="font-size:11px; color:#64748b; margin-bottom:6px;">{item["eng"]}</div>' if item["eng"] else ""
                    rows += f"""
                    <tr><td style="padding:12px 15px; border-bottom:1px solid #e5e7eb; background:#fff;">
                        <div style="font-size:14px; font-weight:bold; color:#1e293b; margin-bottom:4px; line-height:1.4;">{item['chi']}</div>
                        {eng_html}
                        <div style="font-size:11px; color:#94a3b8; display:flex; justify-content:space-between;">
                            <span><b>{item['source']}</b> | {item['date']}</span>
                            <a href="{item['url']}" style="color:{sec_info['color']}; text-decoration:none; font-weight:bold;">详情 →</a>
                        </div>
                    </td></tr>"""
        rows += '<tr><td style="height:10px; background:#f8fafc;"></td></tr>'
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
                <h1 style="margin:0; font-size:22px;">Alex Agent: 教育 & AI 垂直情报</h1>
                <p style="font-size:13px; margin-top:10px; opacity:0.9;">14天中国名校、C9高校政策及全球趋势追踪</p>
                <div style="margin-top:12px; font-size:11px; background:rgba(255,255,255,0.2); display:inline-block; padding:4px 15px; border-radius:20px;">
                    中国分区：{sum(len(v['china']) for v in data.values())} 条 | 国际分区：{sum(len(v['intl']) for v in data.values())} 条
                </div>
            </div>
            <table style="width:100%; border-collapse:collapse;">{content}</table>
        </div></body></html>"""

    msg = MIMEMultipart()
    msg['Subject'] = f"Alex Agent: 14天教育垂直情报 ({datetime.now().strftime('%m/%d')})"
    msg['From'] = f"Alex Edu Intel <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, pw)
        server.send_message(msg)
    print(f"✅ 发送完毕。总计 {total} 条新闻。")

if __name__ == "__main__":
    send_email()
