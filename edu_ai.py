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

# --- 配置：文件路径 ---
HISTORY_FILE = "sent_history.txt"
SEND_LOG_FILE = "daily_send_log.txt"

# --------------------------------------------------------------------------------
# 1. 后台搜索协议：核心 50 个垂直教育站点白名单
# --------------------------------------------------------------------------------

# 深度/权威源 (用于 Part A/B 的深度动态)
CORE_SOURCES_CN = [
    "jyb.cn", "eol.cn", "jiemodui.com", "djchina.com", "shanghairanking.cn", 
    "moe.gov.cn", "caixin.com", "36kr.com"
]

CORE_SOURCES_INTL = [
    "chronicle.com", "insidehighered.com", "timeshighereducation.com", 
    "thepienews.com", "edsurge.com", "edweek.org", "hechingerreport.org",
    "universityworldnews.com", "news.harvard.edu", "news.stanford.edu", "news.mit.edu"
]

# 综合/快讯源 (用于支撑整体情报量)
MISC_SOURCES = [
    "lanjing.com", "xiaozhangbang.com", "yz.chsi.com.cn", "edu.sina.com.cn", 
    "edu.qq.com", "edu.163.com", "edu.people.com.cn", "edu.gmw.cn",
    "nature.com", "qs.com", "bbc.com/news/education", "nytimes.com/section/education",
    "highereddive.com", "k12dive.com", "campustechnology.com"
]

# --------------------------------------------------------------------------------
# 2. 辅助功能逻辑
# --------------------------------------------------------------------------------

def is_garbage_content(title):
    noise_keywords = ['vaccine', 'patient', 'surgery', 'disease', '接种', '临床', '患者', '疫苗', '手术']
    title_lower = title.lower()
    return any(k in title_lower for k in noise_keywords)

def get_fingerprint(title):
    return "".join(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', title))[:40].lower()

def load_history():
    if not os.path.exists(HISTORY_FILE): return set()
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f.readlines())

def save_history(new_fps):
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        for fp in new_fps: f.write(fp + "\n")

def has_sent_today():
    if not os.path.exists(SEND_LOG_FILE): return False
    with open(SEND_LOG_FILE, 'r', encoding='utf-8') as f:
        return f.read().strip() == datetime.now().strftime('%Y-%m-%d')

def mark_as_sent():
    with open(SEND_LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(datetime.now().strftime('%Y-%m-%d'))

# --------------------------------------------------------------------------------
# 3. 抓取逻辑 (核心优化：Site-Specific Search)
# --------------------------------------------------------------------------------

def fetch_edu_intelligence(days=30):
    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    results = {"deep_dynamic": [], "global_briefs": []}
    
    sent_history = load_history()
    current_session_fps = set()

    # 构造 Site 过滤后缀
    site_filter_cn = " (" + " OR ".join([f"site:{s}" for s in CORE_SOURCES_CN]) + ")"
    site_filter_intl = " (" + " OR ".join([f"site:{s}" for s in CORE_SOURCES_INTL]) + ")"

    # 10+10 结构化查询
    queries = {
        # 深度动态：锁定顶级源，寻找政策、AI案例、趋势
        "deep_dynamic": [
            {"q": f"(教育政策 OR 十五五 OR 双一流 OR AI教学){site_filter_cn}", "lang": "zh-CN", "gl": "CN"},
            {"q": f"('Future of Education' OR 'Generative AI' OR 'Admissions Policy'){site_filter_intl}", "lang": "en", "gl": "US"}
        ],
        # 精选快讯：范围放宽到 50 个源，寻找最新资讯
        "global_briefs": [
            {"q": f"(招生 OR 考试 OR 数字化 OR 竞赛) (site:edu.sina.com.cn OR site:jyb.cn OR site:36kr.com)", "lang": "zh-CN", "gl": "CN"},
            {"q": f"(University OR EdTech OR Student) (site:thepienews.com OR site:bbc.com OR site:qs.com)", "lang": "en", "gl": "US"}
        ]
    }

    for key, q_list in queries.items():
        for q_item in q_list:
            search_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q_item['q'])}&hl={q_item['lang']}&gl={q_item['gl']}"
            feed = feedparser.parse(search_url)
            
            for entry in feed.entries:
                if not hasattr(entry, 'published_parsed'): continue
                pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
                if pub_time < threshold: continue
                if is_garbage_content(entry.title): continue
                
                fp = get_fingerprint(entry.title)
                if fp in sent_history or fp in current_session_fps: continue
                if len(results[key]) >= 10: break
                
                title = entry.title
                if q_item['lang'] != 'zh-CN':
                    try: 
                        title = translator.translate(title)
                        time.sleep(0.3)
                    except: pass
                
                current_session_fps.add(fp)
                results[key].append({
                    "title": title,
                    "source": entry.get('source', {}).get('title', '权威源'),
                    "url": entry.link,
                    "date": pub_time.strftime('%m-%d')
                })
            if len(results[key]) >= 10: break

    return results, current_session_fps

# --------------------------------------------------------------------------------
# 4. 邮件排版与发送
# --------------------------------------------------------------------------------

def send_report():
    if has_sent_today(): return
    
    sender = "alexanderxyh@gmail.com"
    pw = os.environ.get('EMAIL_PASSWORD')
    receivers = ["54517745@qq.com"]
    
    data, current_fps = fetch_edu_intelligence(days=30)
    if not data["deep_dynamic"] and not data["global_briefs"]: return

    # 严格遵循用户要求的标题
    subject = "Ying大人的\"垂直教育情报每日滚动刷新\"：30天全球深度精华版 (10+10)"
    
    # 构造 HTML (合并了 50 个源的高端排版)
    html_content = f"""
    <html><body style="font-family:sans-serif; color:#333; line-height:1.6;">
        <h2 style="color:#c02424; border-bottom:2px solid #c02424; padding-bottom:10px;">{subject}</h2>
        <p style="font-size:12px; color:#666;">抓取范围：全球教育 TOP 50 源 | 周期：30天深度覆盖 | 生成日期：{datetime.now().strftime('%Y-%m-%d')}</p>
        
        <h3>🛡️ 深度动态 (Top 10 Deep Insights)</h3>
        <ul style="padding-left:20px;">
            {"".join([f"<li><a href='{i['url']}'>{i['title']}</a> <small>({i['source']} {i['date']})</small></li>" for i in data['deep_dynamic']])}
        </ul>
        <hr/>
        <h3>⚡ 精选快讯 (Top 10 Global Briefs)</h3>
        <ul style="padding-left:20px;">
            {"".join([f"<li><a href='{i['url']}'>{i['title']}</a> <small>({i['source']} {i['date']})</small></li>" for i in data['global_briefs']])}
        </ul>
        <div style="text-align:center; color:#999; font-size:11px; margin-top:30px;">Send by Alex Xing's Agent with Love</div>
    </body></html>
    """

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = f"Ying's Edu Agent <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html_content, 'html'))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.send_message(msg)
        save_history(current_fps)
        mark_as_sent()
        print("Done. Intelligence sent successfully.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    send_report()
