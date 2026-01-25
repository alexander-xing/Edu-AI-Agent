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
# 1. 垂直源白名单协议 (50个核心源 + 关键词校准)
# --------------------------------------------------------------------------------

# 50个垂直域名白名单
EDU_DOMAINS = [
    'jyb.cn', 'eol.cn', 'jiemodui.com', 'djchina.com', 'moe.gov.cn', 'shanghairanking.cn',
    'lanjing.com', 'xiaozhangbang.com', '36kr.com', 'caixin.com', 'people.com.cn',
    'chronicle.com', 'insidehighered.com', 'timeshighereducation.com', 'thepienews.com',
    'edsurge.com', 'edweek.org', 'hechingerreport.org', 'universityworldnews.com',
    'harvard.edu', 'stanford.edu', 'mit.edu', 'ox.ac.uk', 'cam.ac.uk', 'nature.com',
    'campustechnology.com', 'highereddive.com', 'k12dive.com', 'edsource.org'
]

# 必须排除的杂讯词
BLACK_LIST = ['疫苗', '患者', '手术', '病毒', 'vaccine', 'patient', 'clinical', 'surgery', 'hospital']

# --------------------------------------------------------------------------------
# 2. 核心过滤与记忆函数
# --------------------------------------------------------------------------------

def is_valid_edu(title, link):
    """判定内容是否符合 Ying大人的垂直要求"""
    title_l = title.lower()
    # 1. 排除医疗噪音
    if any(b in title_l for b in BLACK_LIST): return False
    # 2. 域名白名单判定：只要是白名单里的，直接算高价值
    if any(domain in link.lower() for domain in EDU_DOMAINS): return True
    # 3. 关键词辅助判定：非白名单的，必须包含教育关键词
    keywords = ['教育', '学校', '招生', '录取', '学科', 'AI', 'Education', 'University', 'Student']
    return any(k.lower() in title_l for k in keywords)

def get_fingerprint(title):
    """指纹去重"""
    return "".join(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', title))[:40].lower()

def load_history():
    if not os.path.exists(HISTORY_FILE): return set()
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f.readlines())

def save_history(new_fps):
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        for fp in new_fps: f.write(fp + "\n")

# --------------------------------------------------------------------------------
# 3. 10+10 抓取引擎
# --------------------------------------------------------------------------------

def fetch_edu_intelligence(days=30):
    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    results = {"deep": [], "briefs": []}
    
    sent_history = load_history()
    current_session_fps = set()

    # 检索任务
    tasks = [
        # Part A: 聚焦深度、政策
        {"q": "教育政策 OR AI教学 OR 学科建设", "lang": "zh-CN", "gl": "CN", "cat": "deep"},
        {"q": "Higher Education AND (Strategy OR AI OR Policy)", "lang": "en", "gl": "US", "cat": "deep"},
        # Part B: 聚焦快讯、动态
        {"q": "招生录取 OR 大学动态 OR 留学", "lang": "zh-CN", "gl": "CN", "cat": "briefs"},
        {"q": "University World News AND Admissions", "lang": "en", "gl": "US", "cat": "briefs"}
    ]

    for task in tasks:
        query = task['q']
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl={task['lang']}&gl={task['gl']}"
        feed = feedparser.parse(url)
        
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold: continue
            
            # 质量过滤
            if not is_valid_edu(entry.title, entry.link): continue
            
            # 指纹去重
            fp = get_fingerprint(entry.title)
            if fp in sent_history or fp in current_session_fps: continue
            
            if len(results[task['cat']]) >= 10: break
            
            # 翻译
            title = entry.title
            if task['lang'] != 'zh-CN':
                try: 
                    title = translator.translate(title)
                    time.sleep(0.3)
                except: pass
            
            current_session_fps.add(fp)
            results[task['cat']].append({
                "title": title,
                "source": entry.get('source', {}).get('title', '教育源'),
                "url": entry.link,
                "date": pub_time.strftime('%m-%d')
            })
            
    return results, current_session_fps

# --------------------------------------------------------------------------------
# 4. 邮件排版与自动化发送
# --------------------------------------------------------------------------------

def send_report():
    # 1. 检查今日日期锁
    if os.path.exists(SEND_LOG_FILE):
        with open(SEND_LOG_FILE, 'r') as f:
            if f.read().strip() == datetime.now().strftime('%Y-%m-%d'):
                print("今日情报已发，跳过执行。")
                return

    # 2. 账号设置 (请确保 EMAIL_PASSWORD 已设为环境变量)
    sender = "alexanderxyh@gmail.com"
    pw = os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com", "ying.xia@wlsafoundation.com"]
    
    # 3. 抓取数据
    data, current_fps = fetch_edu_intelligence(days=30)
    if not data['deep'] and not data['briefs']:
        print("未抓取到符合垂直度要求的内容，检查网络或信源。")
        return

    # 邮件标题
    subject = "Ying大人的'垂直教育情报每日滚动刷新'：30天全球深度精华版 (10+10)"
    
    # 4. 构造 HTML 邮件
    html_items_a = "".join([f"<li style='margin-bottom:10px;'><a href='{i['url']}' style='color:#c02424; font-weight:bold;'>{i['title']}</a><br><small style='color:#666;'>{i['source']} | {i['date']}</small></li>" for i in data['deep']])
    html_items_b = "".join([f"<li style='margin-bottom:10px;'><a href='{i['url']}' style='color:#1a365d; text-decoration:none;'>{i['title']}</a><br><small style='color:#666;'>{i['source']} | {i['date']}</small></li>" for i in data['briefs']])

    email_body = f"""
    <html><body style="font-family:'PingFang SC', sans-serif; line-height:1.6; color:#333;">
        <div style="max-width:700px; margin:0 auto; border:1px solid #ddd; padding:20px; border-radius:10px;">
            <h2 style="text-align:center; color:#c02424;">{subject}</h2>
            <p style="text-align:center; font-size:12px; color:#999;">30天全量追踪 | 白名单域名匹配模式 | {datetime.now().strftime('%Y-%m-%d')}</p>
            
            <div style="background:#fdf2f2; padding:15px; border-radius:8px; margin-bottom:20px;">
                <h3 style="margin-top:0; color:#c02424;">🏛️ PART A: 深度动态 (Top 10 Insights)</h3>
                <ul>{html_items_a if html_items_a else "<li>暂无更新</li>"}</ul>
            </div>
            
            <div style="background:#f4f7fa; padding:15px; border-radius:8px;">
                <h3 style="margin-top:0; color:#1a365d;">⚡ PART B: 精选快讯 (Top 10 Briefs)</h3>
                <ul>{html_items_b if html_items_b else "<li>暂无更新</li>"}</ul>
            </div>
            
            <div style="text-align:center; margin-top:30px; font-size:12px; color:#999; font-style:italic;">
                Send by Alex Xing's Agent with Love
            </div>
        </div>
    </body></html>
    """

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = f"Ying's Edu Agent <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(email_body, 'html'))

    # 5. 发送
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.send_message(msg)
        save_history(current_fps)
        with open(SEND_LOG_FILE, 'w') as f: f.write(datetime.now().strftime('%Y-%m-%d'))
        print("✅ 发送成功！")
    except Exception as e:
        print(f"❌ 发送失败: {e}")

if __name__ == "__main__":
    send_report()
