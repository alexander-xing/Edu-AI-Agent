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

def get_title_fingerprint(title):
    clean_title = re.sub(r' - [^|-]+$| \| [^|-]+$', '', title)
    return "".join(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', clean_title)).lower()

def fetch_edu_news(days=14):
    # 核心源池（区分中国重点和国际重点）
    china_sources = ['"Ministry of Education China"', '"China Daily Education"', '"Global Times Education"', '"新学说"', '"顶思"', '"国际教育洞察"', '"International School Beijing"', '"Shanghai Education"']
    intl_sources = ['"College Board"', 'NACAC', 'UCAS', '"Common App"', 'IBO', '"Cambridge International"', 'Keystone', '"Inside Higher Ed"']
    
    sections = {
        "policy": {"name": "升学、政策与形势", "icon": "🎓", "color": "#1e3a8a", "keywords": ["policy", "admissions", "visa", "sat", "ap", "ib", "ucas", "curriculum", "gaokao", "enrollment"]},
        "ai": {"name": "AI 与教学实践", "icon": "🤖", "color": "#4338ca", "keywords": ["ai", "chatgpt", "intelligence", "digital", "technology", "edtech", "generative", "smart education"]},
        "market": {"name": "区域动态与行业洞察", "icon": "🌏", "color": "#0369a1", "keywords": ["trend", "market", "insight", "shanghai", "global", "report", "analysis", "growth"]}
    }

    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    all_data = {k: {"china": [], "intl": []} for k in sections.keys()}
    
    seen_urls = set()
    seen_fingerprints = set()

    # 抓取逻辑：分别针对中国源和国际源进行扫描
    search_plans = [("china", china_sources), ("intl", intl_sources)]

    for region_id, source_list in search_plans:
        for source in source_list:
            # 这里的 q 包含源名称，确保精准抓取该站动态
            encoded_query = urllib.parse.quote(source)
            # 针对中国源，尝试获取中文版结果（如果源是中文名）
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans" if '"' not in source else f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
            
            feed = feedparser.parse(rss_url)
            
            for entry in feed.entries:
                if not hasattr(entry, 'published_parsed'): continue
                pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
                if pub_time < threshold: continue
                
                if entry.link in seen_urls: continue
                fingerprint = get_title_fingerprint(entry.title)
                if fingerprint in seen_fingerprints: continue
                
                seen_urls.add(entry.link)
                seen_fingerprints.add(fingerprint)
                
                title_lower = entry.title.lower()
                target_sec = "market"
                for sec_id, info in sections.items():
                    if any(k in title_lower for k in info["keywords"]):
                        target_sec = sec_id
                        break
                
                # 二次校验：如果该新闻在国际源抓到但提到了中国，自动归入中国动态
                actual_region = region_id
                if region_id == "intl" and any(k in title_lower for k in ["china", "shanghai", "beijing", "chinese"]):
                    actual_region = "china"

                if len(all_data[target_sec][actual_region]) < 20:
                    try:
                        # 只有非中文标题才翻译
                        chi_title = translator.translate(entry.title) if not any('\u4e00' <= char <= '\u9fff' for char in entry.title) else entry.title
                    except:
                        chi_title = entry.title
                    
                    all_data[target_sec][actual_region].append({
                        "chi": chi_title, "eng": entry.title, "url": entry.link,
                        "source": entry.source.get('title', '权威源'), "date": pub_time.strftime('%m-%d')
                    })
            time.sleep(0.3)

    return all_data, sections

def format_html(data, sections):
    rows = ""
    for sec_id, sec_info in sections.items():
        rows += f'<tr><td style="padding:15px; background:{sec_info["color"]}; color:#fff; font-weight:bold; font-size:16px; border-radius:4px 4px 0 0;">{sec_info["icon"]} {sec_info["name"]}</td></tr>'
        for reg_id, reg_name in [("china", "📍 中国动态 (14天热点)"), ("intl", "🌐 国际视野 (14天热点)")]:
            items = data[sec_id][reg_id]
            rows += f'<tr><td style="padding:8px 15px; background:#f1f5f9; font-weight:bold; color:#475569; font-size:12px; border-left:4px solid {sec_info["color"]};">{reg_name} (已获 {len(items)} 条)</td></tr>'
            if not items:
                rows += '<tr><td style="padding:15px; color:#94a3b8; font-size:12px; background:#fff; text-align:center;">暂无此分区相关动态</td></tr>'
            else:
                for item in items:
                    rows += f"""
                    <tr><td style="padding:12px 15px; border-bottom:1px solid #e5e7eb; background:#fff;">
                        <div style="font-size:14px; font-weight:bold; color:#1e293b; margin-bottom:4px;">{item['chi']}</div>
                        <div style="font-size:11px; color:#64748b; margin-bottom:6px;">{item['eng']}</div>
                        <div style="font-size:11px; color:#94a3b8; display:flex; justify-content:space-between;">
                            <span><b>{item['source']}</b> | {item['date']}</span>
                            <a href="{item['url']}" style="color:{sec_info['color']}; text-decoration:none; font-weight:bold;">详情 →</a>
                        </div>
                    </td></tr>"""
        rows += '<tr><td style="height:15px; background:#f8fafc;"></td></tr>'
    return rows

def send_email():
    sender, pw = "alexanderxyh@gmail.com", os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com"]
    data, sections = fetch_edu_news(days=14)
    total = sum(len(v['china']) + len(v['intl']) for v in data.values())
    content = format_html(data, sections)
    
    html = f"""<html><body style="font-family:Arial,sans-serif; background:#f8fafc; padding:10px;">
        <div style="max-width:700px; margin:0 auto; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.05); border:1px solid #e2e8f0;">
            <div style="background:#1a365d; padding:40px 20px; text-align:center; color:#fff;">
                <h1 style="margin:0; font-size:24px;">全球教育 & AI 动态情报</h1>
                <p style="font-size:14px; margin-top:10px; opacity:0.9;">Agent速递：14天深度全量版</p>
                <div style="margin-top:12px; font-size:12px; background:rgba(255,255,255,0.2); display:inline-block; padding:4px 15px; border-radius:20px;">
                    今日情报总量：{total} 条
                </div>
            </div>
            <table style="width:100%; border-collapse:collapse;">{content}</table>
        </div></body></html>"""

    msg = MIMEMultipart()
    msg['Subject'] = "Agent速递：全球14天AI与教育洞察"
    msg['From'] = f"Alex Edu Intel <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, pw)
        server.send_message(msg)
    print(f"✅ 发送成功，共计 {total} 条新闻。")

if __name__ == "__main__":
    send_email()
