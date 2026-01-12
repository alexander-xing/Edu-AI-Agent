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
    """提取标题核心指纹，过滤掉媒体后缀和特殊符号，防止重复新闻"""
    clean_title = re.sub(r' - [^|-]+$| \| [^|-]+$', '', title)
    return "".join(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', clean_title)).lower()

def fetch_edu_news(days=14):
    # 扩大至14天，并增强搜索源
    sources = ['"College Board"', 'NACAC', 'UCAS', '"Common App"', 'IBO', '"Cambridge International"', '"新学说"', '"顶思"', '"国际教育洞察"', 'Keystone']
    
    sections = {
        "policy": {"name": "升学、政策与形势", "icon": "🎓", "color": "#1e3a8a", "keywords": ["policy", "admissions", "enrollment", "visa", "sat", "ap", "ib", "ucas", "curriculum"]},
        "ai": {"name": "AI 与教学实践", "icon": "🤖", "color": "#4338ca", "keywords": ["ai", "chatgpt", "intelligence", "digital", "technology", "edtech", "generative"]},
        "market": {"name": "区域动态与行业洞察", "icon": "🌏", "color": "#0369a1", "keywords": ["trend", "market", "insight", "shanghai", "china", "global", "report", "analysis", "school"]}
    }

    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    all_data = {k: {"china": [], "intl": []} for k in sections.keys()}
    
    seen_urls = set()
    seen_fingerprints = set()

    print(f"开始抓取过去 {days} 天的教育动态...")

    for source in sources:
        # 对每个源进行抓取，确保覆盖面
        encoded_query = urllib.parse.quote(source)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold: continue
            
            # 去重检测
            if entry.link in seen_urls: continue
            fingerprint = get_title_fingerprint(entry.title)
            if fingerprint in seen_fingerprints: continue
            
            seen_urls.add(entry.link)
            seen_fingerprints.add(fingerprint)
            
            title_lower = entry.title.lower()
            
            # 自动归类逻辑：优先匹配 AI 和 政策，其余归入 行业洞察
            target_sec = "market"
            for sec_id, info in sections.items():
                if any(k in title_lower for k in info["keywords"]):
                    target_sec = sec_id
                    break
            
            # 区分中国与国际：根据标题中的地名或源名判断
            is_china = any(k in title_lower for k in ["china", "shanghai", "beijing", "chinese", "hong kong", "新学说", "顶思", "国际教育"])
            region = "china" if is_china else "intl"
            
            # 限制每个子分区不超过 20 条
            if len(all_data[target_sec][region]) < 20:
                try:
                    # 翻译标题
                    chi_title = translator.translate(entry.title)
                except:
                    chi_title = entry.title
                
                all_data[target_sec][region].append({
                    "chi": chi_title, 
                    "eng": entry.title, 
                    "url": entry.link,
                    "source": entry.source.get('title', '权威教育源'), 
                    "date": pub_time.strftime('%m-%d')
                })
        time.sleep(0.3)

    return all_data, sections

def format_html(data, sections):
    rows = ""
    for sec_id, sec_info in sections.items():
        # 大板块标题
        rows += f'<tr><td style="padding:15px; background:{sec_info["color"]}; color:#fff; font-weight:bold; font-size:16px;">{sec_info["icon"]} {sec_info["name"]}</td></tr>'
        
        for reg_id, reg_name in [("china", "📍 中国动态 (14天热点)"), ("intl", "🌐 国际视野 (14天热点)")]:
            items = data[sec_id][reg_id]
            # 子栏目条
            rows += f'<tr><td style="padding:8px 15px; background:#f1f5f9; font-weight:bold; color:#475569; font-size:12px; border-left:4px solid {sec_info["color"]};">{reg_name}</td></tr>'
            
            if not items:
                rows += '<tr><td style="padding:15px; color:#94a3b8; font-size:12px; background:#fff; text-align:center;">该区间暂无满足条件的新闻更新</td></tr>'
            else:
                for item in items:
                    rows += f"""
                    <tr><td style="padding:12px 15px; border-bottom:1px solid #e5e7eb; background:#fff;">
                        <div style="font-size:14px; font-weight:bold; color:#1e293b; margin-bottom:4px; line-height:1.4;">{item['chi']}</div>
                        <div style="font-size:11px; color:#64748b; margin-bottom:6px;">{item['eng']}</div>
                        <div style="font-size:11px; color:#94a3b8; display:flex; justify-content:space-between;">
                            <span><b>{item['source']}</b> | {item['date']}</span>
                            <a href="{item['url']}" style="color:{sec_info['color']}; text-decoration:none; font-weight:bold;">阅读全文 →</a>
                        </div>
                    </td></tr>"""
        rows += '<tr><td style="height:15px; background:#f8fafc;"></td></tr>'
    return rows

def send_email():
    sender, pw = "alexanderxyh@gmail.com", os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com"]
    
    # 抓取数据
    data, sections = fetch_edu_news(days=14)
    total = sum(len(v['china']) + len(v['intl']) for v in data.values())
    
    # 构建 HTML
    content = format_html(data, sections)
    
    html = f"""
    <html><body style="font-family:'PingFang SC',Arial,sans-serif; background:#f8fafc; padding:10px;">
        <div style="max-width:700px; margin:0 auto; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.05); border:1px solid #e2e8f0;">
            <div style="background:#1a365d; padding:40px 20px; text-align:center; color:#fff;">
                <h1 style="margin:0; font-size:24px;">全球教育 & AI 动态情报</h1>
                <p style="font-size:14px; margin-top:10px; opacity:0.9;">Agent速递：过去14天全量深度观察</p>
                <div style="margin-top:15px; font-size:12px; background:rgba(255,255,255,0.2); display:inline-block; padding:5px 15px; border-radius:20px;">
                    本次情报总量：{total} 条去重精华
                </div>
            </div>
            <table style="width:100%; border-collapse:collapse;">{content}</table>
            <div style="padding:20px; text-align:center; font-size:11px; color:#94a3b8; background:#f8fafc;">
                数据源：CB, NACAC, UCAS, 新学说, 顶思, IBO, Cambridge 等<br>
                覆盖：美、英、加、澳、新、中、日、德、法
            </div>
        </div>
    </body></html>"""

    msg = MIMEMultipart()
    msg['Subject'] = "Agent速递：全球14天AI与教育洞察"
    msg['From'] = f"Alex Edu Intel <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, pw)
        server.send_message(msg)
    print(f"✅ 14天深度情报已发送，共计 {total} 条内容。")

if __name__ == "__main__":
    send_email()
