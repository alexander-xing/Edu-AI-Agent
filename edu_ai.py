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

# --- 配置：记忆文件路径 ---
HISTORY_FILE = "sent_history.txt"

# --------------------------------------------------------------------------------
# 1. 核心过滤与“记忆”逻辑
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
    return "".join(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', title))[:40].lower()

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f.readlines())

def save_history(new_fps):
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        for fp in new_fps:
            f.write(fp + "\n")

# --------------------------------------------------------------------------------
# 2. 邮件排版函数 (补全你漏掉的部分)
# --------------------------------------------------------------------------------

def format_html_refined(data):
    html = ""
    mapping = [
        ("cn_policy", "🏛️ 政策与教育家洞察", "#c02424"),
        ("cn_c9", "🎓 C9名校招生动态", "#c02424"),
        ("cn_highschool", "🏫 1梯队国际高中", "#c02424"),
        ("cn_ai_case", "🤖 国内AI教学实践", "#c02424"),
        ("intl_admission", "🌍 TOP50招生政策", "#1a365d"),
        ("intl_ai_case", "💡 海外AI教学案例", "#1a365d"),
        ("intl_expert", "🔭 国际趋势与观点", "#1a365d")
    ]
    for key, label, color in mapping:
        if key == "cn_policy": 
            html += f'<tr><td style="padding:20px 0 10px 0; font-size:18px; font-weight:bold; color:{color}; border-bottom:2px solid {color};">PART A：中国教育洞察</td></tr>'
        if key == "intl_admission":
            html += f'<tr><td style="padding:30px 0 10px 0; font-size:18px; font-weight:bold; color:{color}; border-bottom:2px solid {color};">PART B：国外教育洞察</td></tr>'
        html += f'<tr><td style="padding:15px 0;"><div style="background:#fff; border:1px solid #e2e8f0; border-radius:8px; overflow:hidden; box-shadow:0 2px 4px rgba(0,0,0,0.05);">'
        html += f'<div style="background:{color}; color:#fff; padding:8px 15px; font-size:14px; font-weight:bold;">{label}</div>'
        html += '<table style="width:100%; border-collapse:collapse;">'
        items = data.get(key, [])
        if not items:
            html += '<tr><td style="padding:15px; font-size:13px; color:#94a3b8;">本期暂无匹配的高价值情报</td></tr>'
        else:
            for item in items:
                html += f"<tr><td style='padding:12px 15px; border-bottom:1px solid #f1f5f9;'><a href='{item['url']}' style='text-decoration:none; color:#1e293b; font-size:14px; line-height:1.5; display:block; font-weight:500;'>{item['title']}</a><div style='font-size:11px; color:#94a3b8; margin-top:6px;'>🏢 {item['source']} | 📅 {item['date']}</div></td></tr>"
        html += '</table></div></td></tr>'
    return html

# --------------------------------------------------------------------------------
# 3. 抓取逻辑
# --------------------------------------------------------------------------------

def fetch_edu_intelligence(days=30):
    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    results = {"cn_policy": [], "cn_c9": [], "cn_highschool": [], "cn_ai_case": [], "intl_admission": [], "intl_ai_case": [], "intl_expert": []}
    sent_history = load_history()
    current_session_fps = set()
    cn_queries = {
        "cn_policy": '(教育部 OR 国务院) (教育政策 OR 评价改革 OR 十五五规划) OR "教育家" (未来教育 OR 洞察)',
        "cn_c9": '(清华 OR 北大 OR 浙大 OR 复旦 OR 上海交大 OR 南大 OR 中科大 OR 西交 OR 哈工大) (招生政策 OR AI专业 OR 录取 OR 学科建设)',
        "cn_highschool": '(人大附 OR 北京四中 OR 上海平和 OR 包玉刚 OR 深国交 OR 杭外 OR 南外 OR WLSA) (升学榜单 OR 招生简章 OR 开放日)',
        "cn_ai_case": '(中学 OR 初中 OR 高中) (AI教学 OR 智慧课堂 OR 数字化转型 OR 人工智能通识课) 案例'
    }
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
            if is_garbage_content(entry.title): continue
            fp = get_fingerprint(entry.title)
            if fp in sent_history or fp in current_session_fps: continue
            if len(results[target_key]) >= 10: break 
            title = entry.title
            if lang != 'zh-CN':
                try: 
                    title = translator.translate(title)
                    time.sleep(0.3)
                except: pass
            current_session_fps.add(fp)
            results[target_key].append({"title": title, "source": entry.get('source', {}).get('title', '权威源'), "url": entry.link, "date": pub_time.strftime('%m-%d')})
        time.sleep(1)

    for k in cn_queries.keys(): process_feed(cn_queries, k, 'zh-CN', 'CN')
    for k in intl_queries.keys(): process_feed(intl_queries, k, 'en-US', 'US')
    save_history(current_session_fps)
    return results

def send_intelligence_report():
    sender, pw = "alexanderxyh@gmail.com", os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com", "ying.xia@wlsafoundation.com"]
    data = fetch_edu_intelligence(days=30)
    total_items = sum(len(v) for v in data.values())
    if total_items == 0:
        print("📭 今日无新增情报，跳过邮件发送。")
        return
    content_rows = format_html_refined(data)
    heart_html = """<div style="text-align: center; margin-top: 40px;"><div style="display: inline-block; position: relative; width: 50px; height: 45px;"><div style="position: absolute; width: 25px; height: 40px; background: #f43f5e; border-radius: 50px 50px 0 0; transform: rotate(-45deg); left: 13px; transform-origin: 0 100%;"></div><div style="position: absolute; width: 25px; height: 40px; background: #f43f5e; border-radius: 50px 50px 0 0; transform: rotate(45deg); left: -12px; transform-origin: 100% 100%;"></div></div></div>"""
    subject = f"Ying大人的'垂直教育情报每日滚动刷新'：30天全球深度精华版 (10+10)"
    email_template = f"""<html><body style="font-family:'PingFang SC',sans-serif; background:#f4f7f9; padding:20px;"><div style="max-width:700px; margin:0 auto;"><div style="text-align:center; padding-bottom:20px;"><h2 style="color:#1e293b; margin:0;">{subject}</h2><p style="font-size:12px; color:#64748b; margin-top:5px;">跨天去重模式 | 30天全量 | {datetime.now().strftime('%Y-%m-%d')}</p></div><table style="width:100%; border-collapse:collapse;">{content_rows}</table>{heart_html}</div></body></html>"""
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = f"Edu Intelligence Agent <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(email_template, 'html'))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.send_message(msg)
        print(f"✅ 报告已发送，今日新增 {total_items} 条。")
    except Exception as e:
        print(f"❌ 失败: {e}")

if __name__ == "__main__":
    send_intelligence_report()
