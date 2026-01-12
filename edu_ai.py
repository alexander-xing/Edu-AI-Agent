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

def get_core_keywords(title):
    """提取标题核心关键词，用于检测是否为同一事件"""
    # 移除停用词，只保留中英文字符
    clean = "".join(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', title))
    # 取前15个字符作为语义指纹
    return clean[:15].lower()

def fetch_edu_news(days=14):
    # 1. 构建全球顶级源池 (30+10)
    # 国际：前30顶级源 (包含招生官协会、官方考试机构、顶尖教育周刊等)
    intl_sources = [
        'College Board', 'NACAC', 'UCAS', 'Common App', 'IBO', 'Cambridge International', 
        'Times Higher Education', 'QS World University Rankings', 'Inside Higher Ed', 
        'The Chronicle of Higher Education', 'EdSurge', 'Education Week', 'HEPI', 
        'Open Doors IIE', 'QuestBridge', 'Keystone Education', 'World Education News',
        'BBC Education', 'The Guardian Education', 'New York Times Education', 
        'Forbes Education', 'U.S. News Education', 'PIE News', 'Study International'
    ]
    
    # 中国：前10顶级源 (教育部、主流教育频道及垂直媒体)
    china_sources = [
        'Ministry of Education China', 'China Daily Education', 'Global Times Education',
        '新学说', '顶思', '国际教育洞察', '中国教育报', '中国教育在线', '新浪教育', '腾讯教育'
    ]
    
    sections = {
        "policy": {"name": "升学、政策与形势", "icon": "🎓", "color": "#1e3a8a", "keywords": ["policy", "admissions", "visa", "sat", "ap", "ib", "ucas", "curriculum", "gaokao"]},
        "ai": {"name": "AI 与教学实践", "icon": "🤖", "color": "#4338ca", "keywords": ["ai", "chatgpt", "intelligence", "digital", "technology", "edtech", "generative"]},
        "market": {"name": "区域动态与行业洞察", "icon": "🌏", "color": "#0369a1", "keywords": ["trend", "market", "insight", "shanghai", "china", "global", "report", "analysis"]}
    }

    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    all_data = {k: {"china": [], "intl": []} for k in sections.keys()}
    
    seen_fingerprints = set() # 用于“同关键词新闻只留一篇”
    
    print(f"正在从全球 {len(intl_sources)+len(china_sources)} 个顶级源检索...")

    # 循环搜索
    for region_label, source_list in [("china", china_sources), ("intl", intl_sources)]:
        for source in source_list:
            # 编码搜索：源名 + 14天内热点
            q = f'"{source}"'
            encoded_query = urllib.parse.quote(q)
            # 针对中国源使用中文索引，国际源使用英文索引
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
            if any('\u4e00' <= char <= '\u9fff' for char in source):
                rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
            
            feed = feedparser.parse(rss_url)
            
            # Google News 默认按“热度/相关性”排序，我们取每组搜索的第一条即为该源的热门
            for entry in feed.entries:
                pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
                if pub_time < threshold: continue
                
                # 【关键词去重逻辑】：提取语义指纹
                fingerprint = get_core_keywords(entry.title)
                if fingerprint in seen_fingerprints:
                    continue # 如果该关键词/事件已存在，直接跳过 (保留的是最先抓到的热度最高的一篇)
                
                title_lower = entry.title.lower()
                target_sec = "market"
                for sec_id, info in sections.items():
                    if any(k in title_lower for k in info["keywords"]):
                        target_sec = sec_id
                        break
                
                # 确定区域归属
                actual_region = region_label
                if region_label == "intl" and any(k in title_lower for k in ["china", "shanghai", "beijing"]):
                    actual_region = "china"

                if len(all_data[target_sec][actual_region]) < 20:
                    seen_fingerprints.add(fingerprint)
                    try:
                        # 翻译
                        is_chinese = any('\u4e00' <= char <= '\u9fff' for char in entry.title)
                        chi_title = entry.title if is_chinese else translator.translate(entry.title)
                    except:
                        chi_title = entry.title
                    
                    all_data[target_sec][actual_region].append({
                        "chi": chi_title, "eng": entry.title, "url": entry.link,
                        "source": entry.source.get('title', source), "date": pub_time.strftime('%m-%d')
                    })
            time.sleep(0.2) # 避免频率限制

    return all_data, sections

def format_html(data, sections):
    rows = ""
    for sec_id, sec_info in sections.items():
        rows += f'<tr><td style="padding:15px; background:{sec_info["color"]}; color:#fff; font-weight:bold; font-size:16px;">{sec_info["icon"]} {sec_info["name"]}</td></tr>'
        for reg_id, reg_name in [("china", "📍 中国动态 (Top 10 源)"), ("intl", "🌐 国际视野 (Top 30 源)")]:
            items = data[sec_id][reg_id]
            rows += f'<tr><td style="padding:8px 15px; background:#f1f5f9; font-weight:bold; color:#475569; font-size:12px;">{reg_name}</td></tr>'
            if not items:
                rows += '<tr><td style="padding:15px; color:#94a3b8; font-size:12px; background:#fff; text-align:center;">暂无最新热点</td></tr>'
            else:
                for item in items:
                    rows += f"""
                    <tr><td style="padding:12px 15px; border-bottom:1px solid #e5e7eb; background:#fff;">
                        <div style="font-size:14px; font-weight:bold; color:#1e293b; margin-bottom:4px;">{item['chi']}</div>
                        <div style="font-size:11px; color:#64748b; margin-bottom:6px;">{item['eng']}</div>
                        <div style="font-size:11px; color:#94a3b8;"><b>{item['source']}</b> | {item['date']} | <a href="{item['url']}" style="color:{sec_info['color']}; text-decoration:none; font-weight:bold;">阅读原文 →</a></div>
                    </td></tr>"""
        rows += '<tr><td style="height:10px; background:#f8fafc;"></td></tr>'
    return rows

def send_email():
    sender, pw = "alexanderxyh@gmail.com", os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com"]
    data, sections = fetch_edu_news(days=14)
    total = sum(len(v['china']) + len(v['intl']) for v in data.values())
    content = format_html(data, sections)
    
    html = f"""<html><body style="font-family:Arial,sans-serif; background:#f8fafc; padding:20px;">
        <div style="max-width:750px; margin:0 auto; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.1); border:1px solid #e2e8f0;">
            <div style="background:#1a365d; padding:40px; text-align:center; color:#fff;">
                <h1 style="margin:0; font-size:24px;">全球顶级教育洞察周报</h1>
                <p style="font-size:14px; margin-top:10px; opacity:0.9;">14天热度去重精华版</p>
                <div style="margin-top:15px; font-size:12px; background:rgba(255,255,255,0.2); display:inline-block; padding:5px 20px; border-radius:20px;">
                    数据源涵盖：中/外 Top 40 教育机构与媒体
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
    print(f"✅ 发送完毕。共计去重后新闻 {total} 条。")

if __name__ == "__main__":
    send_email()
