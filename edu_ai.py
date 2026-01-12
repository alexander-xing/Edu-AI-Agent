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
    return clean[:18].lower()

def fetch_edu_news(days=14):
    # 1. 重新定义中国区垂直搜索指令
    # 领域1：知名国际学校 (学校名 + 关键词)
    china_intl_schools = '("包玉刚" OR "平和双语" OR "世外教育" OR "深国交" OR "北京鼎石" OR "贝赛思" OR "惠灵顿" OR "德威") (升学 OR 改革 OR 活动 OR 录取)'
    # 领域2：C9高校及来华留学政策
    c9_and_study_in_china = '("C9联盟" OR "清华大学" OR "北京大学" OR "复旦大学" OR "上海交大") (来华留学 OR 留学生政策 OR 国际生招生)'
    # 领域3：行业发展趋势与政策
    china_edu_trends = '("国际学校" OR "民办教育" OR "中外办学") (政策 OR 趋势 OR 洞察 OR 规范)'

    china_queries = [china_intl_schools, c9_and_study_in_china, china_edu_trends]

    # 2. 定义国际区源池
    intl_sources = ['"College Board"', 'NACAC', 'UCAS', 'IBO', '"Cambridge International"', '"Education Week"', '"Times Higher Education"', 'EdSurge']

    sections = {
        "policy": {"name": "升学、政策与形势", "icon": "🎓", "color": "#1e3a8a", "keywords": ["policy", "admissions", "visa", "sat", "ap", "ib", "ucas", "升学", "招生", "录取"]},
        "ai": {"name": "AI 与教学实践", "icon": "🤖", "color": "#4338ca", "keywords": ["ai", "chatgpt", "intelligence", "technology", "edtech", "人工智能", "数字化"]},
        "market": {"name": "区域动态与行业洞察", "icon": "🌏", "color": "#0369a1", "keywords": ["trend", "market", "insight", "report", "趋势", "动态", "分析", "报告"]}
    }

    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    all_data = {k: {"china": [], "intl": []} for k in sections.keys()}
    seen_fingerprints = set()

    # --- 执行中国区搜索 ---
    for q in china_queries:
        encoded_q = urllib.parse.quote(q)
        rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries:
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold: continue
            
            fingerprint = get_core_fingerprint(entry.title)
            if fingerprint in seen_fingerprints: continue

            # 过滤明显非教育新闻（如房产、纯娱乐等）
            if any(x in entry.title for x in ["房产", "楼盘", "股票", "涨停"]): continue

            # 确定板块
            target_sec = "market" # 默认行业洞察
            title_lower = entry.title.lower()
            if any(k in title_lower for k in sections["policy"]["keywords"]): target_sec = "policy"
            elif any(k in title_lower for k in sections["ai"]["keywords"]): target_sec = "ai"

            if len(all_data[target_sec]["china"]) < 10: # 严格限额10条
                seen_fingerprints.add(fingerprint)
                all_data[target_sec]["china"].append({
                    "chi": entry.title, "eng": "", "url": entry.link,
                    "source": entry.source.get('title', '中国教育动态'), "date": pub_time.strftime('%m-%d')
                })
        time.sleep(0.5)

    # --- 执行国际区搜索 ---
    for src in intl_sources:
        encoded_q = urllib.parse.quote(src)
        rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries:
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold: continue
            
            fingerprint = get_core_fingerprint(entry.title)
            if fingerprint in seen_fingerprints: continue

            target_sec = "market"
            title_lower = entry.title.lower()
            if any(k in title_lower for k in sections["policy"]["keywords"]): target_sec = "policy"
            elif any(k in title_lower for k in sections["ai"]["keywords"]): target_sec = "ai"

            if len(all_data[target_sec]["intl"]) < 10: # 严格限额10条
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
        for reg_id, reg_name in [("china", "📍 中国教育情报 (垂直定向)"), ("intl", "🌐 国际教育视野 (Top 源)")]:
            items = data[sec_id][reg_id]
            rows += f'<tr><td style="padding:8px 15px; background:#f1f5f9; font-weight:bold; color:#475569; font-size:12px;">{reg_name} (Top {len(items)})</td></tr>'
            if not items:
                rows += '<tr><td style="padding:15px; color:#94a3b8; font-size:12px; background:#fff; text-align:center;">暂无匹配的深度情报</td></tr>'
            else:
                for item in items:
                    eng_html = f'<div style="font-size:11px; color:#64748b; margin-bottom:6px;">{item["eng"]}</div>' if item["eng"] else ""
                    rows += f"""
                    <tr><td style="padding:12px 15px; border-bottom:1px solid #e5e7eb; background:#fff;">
                        <div style="font-size:14px; font-weight:bold; color:#1e293b; margin-bottom:4px; line-height:1.4;">{item['chi']}</div>
                        {eng_html}
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
    
    html = f"""<html><body style="font-family:'PingFang SC',Arial,sans-serif; background:#f8fafc; padding:20px;">
        <div style="max-width:750px; margin:0 auto; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.1); border:1px solid #e2e8f0;">
            <div style="background:#1a365d; padding:35px; text-align:center; color:#fff;">
                <h1 style="margin:0; font-size:22px;">国际教育 & AI 垂直情报</h1>
                <p style="font-size:13px; margin-top:10px; opacity:0.9;">针对知名国际学校、C9高校政策及全球趋势深度定制</p>
                <div style="margin-top:12px; font-size:11px; background:rgba(255,255,255,0.2); display:inline-block; padding:4px 15px; border-radius:20px;">
                    数据已去重，每版块限额 10 条精华
                </div>
            </div>
            <table style="width:100%; border-collapse:collapse;">{content}</table>
        </div></body></html>"""

    msg = MIMEMultipart()
    msg['Subject'] = "Alex Agent: 14天垂直教育情报(中国名校/C9/AI)"
    msg['From'] = f"Alex Edu Intel <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html, 'html'))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, pw)
        server.send_message(msg)
    print(f"✅ 发送完毕。总计 {total} 条高相关新闻。")

if __name__ == "__main__":
    send_email()
