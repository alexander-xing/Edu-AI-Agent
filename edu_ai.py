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

def fetch_edu_news(days=7):
    # 统一的高价值源池
    sources = ['"College Board"', 'NACAC', '"Quest Bridge"', '"Open Doors"', 'Keystone', 'UCAS', '"Common App"', '"新学说"', '"顶思"', '"国际教育洞察"']
    
    # 板块定义与识别关键词
    sections = {
        "policy": {"name": "升学、政策与形势", "icon": "🎓", "color": "#1e3a8a", "keywords": ["policy", "admissions", "enrollment", "visa", "sat", "ap", "ib", "ucas", "common app"]},
        "ai": {"name": "AI 与教学实践", "icon": "🤖", "color": "#4338ca", "keywords": ["ai", "chatgpt", "intelligence", "digital", "technology", "edtech"]},
        "market": {"name": "区域动态与行业洞察", "icon": "🌏", "color": "#0369a1", "keywords": ["trend", "market", "insight", "shanghai", "china", "global", "report", "analysis"]}
    }

    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    all_data = {k: {"china": [], "intl": []} for k in sections.keys()}
    seen_urls = set()

    print("开始多轮深度抓取...")

    # 策略：对每一个源进行单独抓取，确保“区域动态与行业洞察”不再落空
    for source in sources:
        query = f"{source}" # 直接搜源站名，保证全量抓取
        encoded_query = urllib.parse.quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time > threshold and entry.link not in seen_urls:
                seen_urls.add(entry.link)
                
                title_lower = entry.title.lower()
                # 自动分类逻辑
                target_sec = "market" # 默认为行业动态
                for sec_id, info in sections.items():
                    if any(k in title_lower for k in info["keywords"]):
                        target_sec = sec_id
                        break
                
                # 区分中国与国际
                region = "china" if any(k in title_lower for k in ["china", "shanghai", "beijing", "chinese", "新学说", "顶思"]) else "intl"
                
                # 限制每个子板块不超过 10 条，防止单一来源刷屏
                if len(all_data[target_sec][region]) < 10:
                    try:
                        chi_title = translator.translate(entry.title)
                    except: chi_title = entry.title
                    
                    all_data[target_sec][region].append({
                        "chi": chi_title, "eng": entry.title, "url": entry.link,
                        "source": entry.source.get('title', '教育源'), "date": pub_time.strftime('%m-%d')
                    })
        time.sleep(0.5)

    return all_data, sections

def format_html(data, sections):
    rows = ""
    for sec_id, sec_info in sections.items():
        rows += f'<tr><td style="padding:15px; background:{sec_info["color"]}; color:#fff; font-weight:bold; font-size:16px; border-radius:4px 4px 0 0;">{sec_info["icon"]} {sec_info["name"]}</td></tr>'
        
        for reg_id, reg_name in [("china", "📍 中国动态"), ("intl", "🌐 国际视野")]:
            items = data[sec_id][reg_id]
            # 即使该子板块为空，也要显示栏目头，确保结构完整
            rows += f'<tr><td style="padding:8px 15px; background:#f1f5f9; font-weight:bold; color:#475569; font-size:12px;">{reg_name}</td></tr>'
            
            if not items:
                rows += '<tr><td style="padding:10px 15px; color:#94a3b8; font-size:12px; background:#fff;">本周暂无特定关联动态</td></tr>'
            else:
                for item in items:
                    rows += f"""
                    <tr><td style="padding:12px 15px; border-bottom:1px solid #e2e8f0; background:#fff;">
                        <div style="font-size:14px; font-weight:bold; color:#1e293b; margin-bottom:4px;">{item['chi']}</div>
                        <div style="font-size:11px; color:#64748b; margin-bottom:6px;">{item['eng']}</div>
                        <div style="font-size:11px; color:#94a3b8;"><b>{item['source']}</b> | {item['date']} | <a href="{item['url']}" style="color:{sec_info['color']}; text-decoration:none; font-weight:bold;">详情 →</a></div>
                    </td></tr>"""
        rows += '<tr><td style="height:15px; background:#f8fafc;"></td></tr>'
    return rows

def send_email():
    sender, pw = "alexanderxyh@gmail.com", os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com"]
    data, sections = fetch_edu_news()
    
    total = sum(len(v['china']) + len(v['intl']) for v in data.values())
    content = format_html(data, sections)
    
    html = f"""<html><body style="font-family:Arial,sans-serif; background:#f8fafc; padding:20px;">
        <div style="max-width:700px; margin:0 auto; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.05); border:1px solid #e2e8f0;">
            <div style="background:#1e3a8a; padding:35px 20px; text-align:center; color:#fff;">
                <h1 style="margin:0; font-size:24px;">全球教育 & AI 动态情报</h1>
                <p style="font-size:14px; margin-top:10px; opacity:0.9;">Agent速递：7天分类深度洞察</p>
                <div style="margin-top:15px; font-size:12px; background:rgba(255,255,255,0.2); display:inline-block; padding:4px 15px; border-radius:20px;">
                    今日情报总量：{total} 条精华
                </div>
            </div>
            <table style="width:100%; border-collapse:collapse;">{content}</table>
            <div style="padding:20px; text-align:center; font-size:11px; color:#94a3b8; background:#f8fafc;">
                抓取源：College Board, NACAC, 新学说, 顶思 等<br>
                覆盖：美、英、加、澳、新、中、日、德、法
            </div>
        </div></body></html>"""

    msg = MIMEMultipart()
    msg['Subject'] = "Agent速递：全球7天AI与教育洞察"
    msg['From'] = f"Alex Edu Intel <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, pw)
        server.send_message(msg)
    print(f"✅ 报告已发送，共计 {total} 条新闻。")

if __name__ == "__main__":
    send_email()
