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
# 1. 核心过滤逻辑：防止干扰内容进入
# --------------------------------------------------------------------------------

def is_garbage_content(title):
    """自动过滤非教育类的高频杂讯"""
    noise_keywords = [
        'vaccine', 'medical', 'clinical', 'patient', 'surgery', 'disease', 
        'vaccination', '接种', '临床', '患者', '疫苗', '手术', '病毒'
    ]
    title_lower = title.lower()
    return any(k in title_lower for k in noise_keywords)

def get_fingerprint(title):
    """提取指纹用于去重"""
    return "".join(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', title))[:30].lower()

# --------------------------------------------------------------------------------
# 2. 垂直情报抓取核心
# --------------------------------------------------------------------------------

def fetch_edu_intelligence(days=14):
    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    results = {
        "cn_policy": [], "cn_c9": [], "cn_highschool": [], "cn_ai_case": [],
        "intl_admission": [], "intl_ai_case": [], "intl_expert": []
    }
    seen_fps = set()
    
    # --- 中国部分 (4个子模块) ---
    cn_queries = {
        "cn_policy": '(教育部 OR 国务院) (教育政策 OR 评价改革 OR 十五五规划) OR "教育家" (未来教育 OR 洞察)',
        "cn_c9": '(清华 OR 北大 OR 浙大 OR 复旦 OR 上海交大 OR 南大 OR 中科大 OR 西交 OR 哈工大) (招生政策 OR AI专业 OR 录取 OR 学科建设)',
        "cn_highschool": '(人大附 OR 北京四中 OR 上海平和 OR 包玉刚 OR 深国交 OR 杭外 OR 南外 OR WLSA) (升学榜单 OR 招生简章 OR 开放日)',
        "cn_ai_case": '(中学 OR 初中 OR 高中) (AI教学 OR 智慧课堂 OR 数字化转型 OR 人工智能通识课) 案例'
    }

    # --- 国际部分 (3个子模块 - 强化排除版) ---
    intl_queries = {
        "intl_admission": 'site:edu (Admissions OR "Entry Requirements") ("Chinese students" OR "International students") "2026" -clinical -medical -vaccine -health',
        "intl_ai_case": '(site:edsurge.com OR site:chronicle.com OR site:edweek.org) "Generative AI" (Classroom OR Curriculum OR "Teaching Practice") -oncology -biotech -protein',
        "intl_expert": 'site:edu ("Future of Higher Education" OR "Educational Trends") (Professor OR Dean OR Provost) -nursing -epidemiology -surgery'
    }

    def process_feed(queries, target_key, lang='zh-CN', gl='CN'):
        q = queries[target_key]
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl={lang}&gl={gl}"
        feed = feedparser.parse(url)
        
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold: continue
            
            # 硬核过滤逻辑
            if is_garbage_content(entry.title): continue
            fp = get_fingerprint(entry.title)
            if fp in seen_fps or len(results[target_key]) >= 5: continue
            
            title = entry.title
            if lang != 'zh-CN':
                try: 
                    title = translator.translate(title)
                    time.sleep(0.3)
                except: pass
            
            seen_fps.add(fp)
            results[target_key].append({
                "title": title,
                "source": entry.get('source', {}).get('title', '权威源'),
                "url": entry.link,
                "date": pub_time.strftime('%m-%d')
            })
        time.sleep(1)

    for k in cn_queries.keys(): process_feed(cn_queries, k, 'zh-CN', 'CN')
    for k in intl_queries.keys(): process_feed(intl_queries, k, 'en-US', 'US')
    
    return results

# --------------------------------------------------------------------------------
# 3. 邮件排版美化 (卡片边框版)
# --------------------------------------------------------------------------------

def format_html_refined(data):
    html = ""
    mapping = [
        ("cn_policy", "🏛️ 政策与教育家洞察", "#c02424"),
        ("cn_c9", "🎓 C9名校招生动态", "#c02424"),
        ("cn_highschool", "🏫 1梯队国高升学", "#c02424"),
        ("cn_ai_case", "🤖 国内AI教学实践", "#c02424"),
        ("intl_admission", "🌍 TOP50招生政策", "#1a365d"),
        ("intl_ai_case", "💡 海外AI教学案例", "#1a365d"),
        ("intl_expert", "🔭 国际趋势与观点", "#1a365d")
    ]
    
    for key, label, color in mapping:
        # 分区大标题
        if key == "cn_policy": 
            html += f'<tr><td style="padding:20px 0 10px 0; font-size:18px; font-weight:bold; color:{color}; border-bottom:2px solid {color};">PART A：中国教育洞察</td></tr>'
        if key == "intl_admission":
            html += f'<tr><td style="padding:30px 0 10px 0; font-size:18px; font-weight:bold; color:{color}; border-bottom:2px solid {color};">PART B：国外教育洞察</td></tr>'
        
        # 子模块卡片容器
        html += f'<tr><td style="padding:15px 0;">'
        html += f'<div style="background:#fff; border:1px solid #e2e8f0; border-radius:8px; overflow:hidden; box-shadow:0 2px 4px rgba(0,0,0,0.05);">'
        html += f'<div style="background:{color}; color:#fff; padding:8px 15px; font-size:14px; font-weight:bold;">{label}</div>'
        html += '<table style="width:100%; border-collapse:collapse;">'
        
        items = data.get(key, [])
        if not items:
            html += '<tr><td style="padding:15px; font-size:13px; color:#94a3b8;">本期暂无匹配的高价值情报</td></tr>'
        else:
            for item in items:
                html += f"""
                <tr><td style="padding:12px 15px; border-bottom:1px solid #f1f5f9;">
                    <a href="{item['url']}" style="text-decoration:none; color:#1e293b; font-size:14px; line-height:1.5; display:block; font-weight:500;">{item['title']}</a>
                    <div style="font-size:11px; color:#94a3b8; margin-top:6px;">🏢 {item['source']} | 📅 {item['date']}</div>
                </td></tr>"""
        
        html += '</table></div></td></tr>'
    return html

def send_intelligence_report():
    sender, pw = "alexanderxyh@gmail.com", os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com"]
    
    print("🛰️ 正在精准抓取 7 大垂直模块，排除无关信息中...")
    data = fetch_edu_intelligence(days=14)
    content_rows = format_html_refined(data)
    
    email_template = f"""
    <html><body style="font-family:'PingFang SC',sans-serif; background:#f4f7f9; padding:20px;">
        <div style="max-width:700px; margin:0 auto;">
            <div style="text-align:center; padding-bottom:20px;">
                <h2 style="color:#1e293b; margin:0;">Ying大人的'垂直教育情报（每日刷新）</h2>
                <p style="font-size:12px; color:#64748b; margin-top:5px;">14天精华追踪 | {datetime.now().strftime('%Y-%m-%d')}</p>
            </div>
            <table style="width:100%; border-collapse:collapse;">{content_rows}</table>
            <div style="padding:30px; text-align:center; font-size:10px; color:#94a3b8;">
                本报告由垂直教育情报 Agent 生成 | 信号源：官方名校网 & 精准教育媒体 | 搜索范围：14天
            </div>
        </div>
    </body></html>"""

    msg = MIMEMultipart()
    msg['Subject'] = f"Ying大人的'垂直教育情报（每日刷新）({datetime.now().strftime('%m/%d')})"
    msg['From'] = f"Edu Intelligence Agent <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(email_template, 'html'))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.send_message(msg)
        print("✅ 报告已成功刷新并美化发送。")
    except Exception as e:
        print(f"❌ 失败: {e}")

if __name__ == "__main__":
    send_intelligence_report()
