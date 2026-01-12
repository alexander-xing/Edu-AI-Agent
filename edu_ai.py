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
    # 统一的基础来源范围
    base_sources = '("College Board" OR NACAC OR "Quest Bridge" OR "Open Doors" OR Keystone OR UCAS OR "Common App" OR "新学说" OR "顶思" OR "国际教育洞察")'
    
    # 定义三个核心板块及其关键词
    sections = [
        {"id": "policy", "name": "升学、政策与形势", "icon": "🎓", "color": "#1e3a8a", "terms": "(Policy OR Admissions OR Enrollment OR Visa OR SAT OR AP OR IB)"},
        {"id": "ai", "name": "AI 与教学实践", "icon": "🤖", "color": "#4338ca", "terms": "(AI OR ChatGPT OR 'Generative AI' OR 'Artificial Intelligence' OR EdTech)"},
        {"id": "market", "name": "区域动态与行业洞察", "icon": "🌏", "color": "#0369a1", "terms": "(Trends OR Market OR Insights OR 'Study Abroad' OR 'Higher Ed')"}
    ]
    
    final_data = {}
    seen_urls = set()
    threshold = datetime.now() - timedelta(days=days)
    translator = GoogleTranslator(source='auto', target='zh-CN')

    for sec in sections:
        # 每个板块区分中国和国外
        final_data[sec['id']] = {"china": [], "intl": []}
        
        # 组合搜索词：基础源 + 板块关键词
        query_base = f"{base_sources} {sec['terms']}"
        
        # 1. 抓取中国相关内容
        q_china = f"{query_base} (China OR Shanghai OR Beijing OR Chinese)"
        # 2. 抓取国际相关内容
        q_intl = f"{query_base} (USA OR UK OR Canada OR Australia OR Global OR Europe)"
        
        for lang_type, q_str in [("china", q_china), ("intl", q_intl)]:
            encoded_query = urllib.parse.quote(q_str)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(rss_url)
            
            count = 0
            for entry in feed.entries:
                pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
                if pub_time > threshold and entry.link not in seen_urls:
                    seen_urls.add(entry.link)
                    try:
                        chi_title = translator.translate(entry.title)
                    except: chi_title = entry.title
                    
                    final_data[sec['id']][lang_type].append({
                        "chi": chi_title, "eng": entry.title, "url": entry.link,
                        "source": entry.source.get('title', 'Edu Source'), "date": pub_time.strftime('%m-%d')
                    })
                    count += 1
                if count >= 8: break # 每个子类取8条，确保大板块总数约15条
            time.sleep(1)
        print(f"✅ 板块【{sec['name']}】抓取完成。")

    return final_data, sections

def format_html(data, sections):
    rows = ""
    for sec in sections:
        # 板块大标题
        rows += f'<tr><td style="padding:15px; background:{sec["color"]}; color:#fff; font-weight:bold; font-size:16px;">{sec["icon"]} {sec["name"]}</td></tr>'
        
        # 子板块：中国与国际
        for sub_type, sub_name in [("china", "📍 中国动态"), ("intl", "🌐 国际视野")]:
            rows += f'<tr><td style="padding:10px 15px; background:#f1f5f9; font-weight:bold; color:#475569; font-size:13px;">{sub_name}</td></tr>'
            
            items = data[sec['id']][sub_type]
            if not items:
                rows += '<tr><td style="padding:10px 15px; color:#94a3b8; font-size:12px;">本周暂无特定关联动态</td></tr>'
            else:
                for item in items:
                    rows += f"""
                    <tr><td style="padding:12px 15px; border-bottom:1px solid #e5e7eb; background:#fff;">
                        <div style="font-size:14px; font-weight:bold; color:#1e293b; margin-bottom:4px;">{item['chi']}</div>
                        <div style="font-size:11px; color:#64748b; margin-bottom:6px;">{item['eng']}</div>
                        <div style="font-size:11px; color:#94a3b8;"><b>{item['source']}</b> | {item['date']} | <a href="{item['url']}" style="color:{sec['color']}; text-decoration:none;">详情 →</a></div>
                    </td></tr>"""
        rows += '<tr><td style="height:15px; background:#f8fafc;"></td></tr>'
    return rows

def send_email():
    sender, pw = "alexanderxyh@gmail.com", os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com"]
    data, sections = fetch_edu_intelligence()
    
    total = sum(len(v['china']) + len(v['intl']) for v in data.values())
    content = format_html(data, sections)
    
    html = f"""<html><body style="font-family:Arial; background:#f8fafc; padding:20px;">
        <div style="max-width:700px; margin:0 auto; background:#fff; border-radius:12px; overflow:hidden; border:1px solid #e2e8f0;">
            <div style="background:#1e3a8a; padding:30px; text-align:center; color:#fff;">
                <h1 style="margin:0; font-size:22px;">全球教育 & AI 动态情报</h1>
                <p style="font-size:14px; margin-top:10px;">Agent速递：7天分类深度洞察 (含中国/国际分区)</p>
                <div style="margin-top:10px; font-size:12px; background:rgba(255,255,255,0.2); display:inline-block; padding:4px 12px; border-radius:20px;">今日推送：{total} 条</div>
            </div>
            <table style="width:100%; border-collapse:collapse;">{content}</table>
        </div></body></html>"""

    msg = MIMEMultipart()
    msg['Subject'] = "Agent速递：全球7天AI与教育洞察"
    msg['From'] = f"Alex Edu Intel <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, pw)
        server.send_message(msg)
    print(f"✅ 报告已发送，共计 {total} 条。")

if __name__ == "__main__":
    send_email()
