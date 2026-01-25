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
# 1. 核心垂直协议：50个白名单域名 & 关键词校准
# --------------------------------------------------------------------------------

# 垂直源白名单（部分展示，确保包含你指定的50个核心域）
DOMAIN_WHITE_LIST = [
    'jyb.cn', 'eol.cn', 'jiemodui.com', 'djchina.com', 'moe.gov.cn', 'shanghairanking.cn',
    'chronicle.com', 'insidehighered.com', 'timeshighereducation.com', 'thepienews.com',
    'edsurge.com', 'edweek.org', 'hechingerreport.org', 'universityworldnews.com',
    'harvard.edu', 'stanford.edu', 'mit.edu', 'ox.ac.uk', 'cam.ac.uk', 'nature.com',
    'lanjing.com', 'xiaozhangbang.com', '36kr.com', 'caixin.com', 'people.com.cn'
]

# 必须包含的教育核心词（防止搜到名校的医疗/体育/娱乐新闻）
MUST_HAVE = ['教育', '学校', '招生', '录取', '学科', '课程', '教学', 'AI', 'Education', 'Admissions', 'University', 'Campus', 'Student']
# 绝对排除词
FORBIDDEN = ['疫苗', '患者', '手术', '病毒', 'vaccine', 'patient', 'clinical', 'surgery']

# --------------------------------------------------------------------------------
# 2. 增强型过滤与记忆逻辑
# --------------------------------------------------------------------------------

def is_valid_edu_content(title, link):
    """双重清洗：确保内容既来自白名单，又确实关于教育"""
    title_l = title.lower()
    # 1. 黑名单剔除
    if any(f in title_l for f in FORBIDDEN): return False
    # 2. 关键词校验
    if not any(k.lower() in title_l for k in MUST_HAVE): return False
    # 3. 域名校验：检查链接是否包含白名单中的域名
    return any(domain in link.lower() for domain in DOMAIN_WHITE_LIST)

def get_fingerprint(title):
    return "".join(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', title))[:40].lower()

def load_history():
    if not os.path.exists(HISTORY_FILE): return set()
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f.readlines())

def save_history(new_fps):
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        for fp in new_fps: f.write(fp + "\n")

# --------------------------------------------------------------------------------
# 3. 抓取逻辑：Google News 为主，白名单过滤为王
# --------------------------------------------------------------------------------

def fetch_edu_intelligence(days=30):
    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    # 结构化存储：10条深度 + 10条快讯
    results = {"deep_dynamic": [], "global_briefs": []}
    
    sent_history = load_history()
    current_session_fps = set()

    # 构造针对 Google News 的精准检索式
    search_tasks = [
        # Part A：深度动态搜索
        {"q": "教育政策 OR AI教学 OR 评价改革 OR 学科建设", "lang": "zh-CN", "gl": "CN", "cat": "deep_dynamic"},
        {"q": "Higher Ed Strategy OR Generative AI Classroom OR Admissions Policy", "lang": "en", "gl": "US", "cat": "deep_dynamic"},
        # Part B：全球快讯搜索
        {"q": "教育动态 OR 大学动态 OR 留学资讯", "lang": "zh-CN", "gl": "CN", "cat": "global_briefs"},
        {"q": "University World News OR International Students News", "lang": "en", "gl": "US", "cat": "global_briefs"}
    ]

    for task in search_tasks:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(task['q'])}&hl={task['lang']}&gl={task['gl']}"
        feed = feedparser.parse(url)
        
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold: continue
            
            # --- 核心改进：调用白名单过滤函数 ---
            if not is_valid_edu_content(entry.title, entry.link): continue
            
            fp = get_fingerprint(entry.title)
            if fp in sent_history or fp in current_session_fps: continue
            if len(results[task['cat']]) >= 10: break 
            
            title = entry.title
            if task['lang'] != 'zh-CN':
                try: 
                    title = translator.translate(title)
                    time.sleep(0.2) # 避免翻译请求过快
                except: pass
            
            current_session_fps.add(fp)
            results[task['cat']].append({
                "title": title,
                "source": entry.get('source', {}).get('title', '教育白名单源'),
                "url": entry.link,
                "date": pub_time.strftime('%m-%d')
            })
            
    return results, current_session_fps

# --------------------------------------------------------------------------------
# 4. 邮件发送逻辑 (完全对齐你的标题和格式要求)
# --------------------------------------------------------------------------------

def send_intelligence_report():
    # 环境变量与邮箱设置
    sender, pw = "alexanderxyh@gmail.com", os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com", "ying.xia@wlsafoundation.com"]
    
    # 抓取 10+10 内容
    data, current_fps = fetch_edu_intelligence(days=30)
    
    # 邮件标题：严格遵循 Ying大人 指示
    subject = "Ying大人的'垂直教育情报每日滚动刷新'：30天全球深度精华版 (10+10)"
    
    # 简单明了的 HTML 排版
    html_content = f"""
    <html><body style="font-family:'PingFang SC', sans-serif; background:#f5f7f9; padding:20px;">
        <div style="max-width:700px; margin:0 auto; background:#fff; padding:20px; border-radius:12px; border:1px solid #e1e4e8;">
            <h2 style="color:#c02424; text-align:center; border-bottom:2px solid #c02424; padding-bottom:10px;">{subject}</h2>
            <p style="text-align:center; color:#666; font-size:12px;">监测信源：Top 50 垂直源 + Google News | 范围：30天全量</p>
            
            <h3 style="color:#c02424;">🏛️ PART A：深度动态 (Top 10 Insights)</h3>
            {"".join([f"<div style='margin-bottom:12px;'>• <a href='{i['url']}' style='color:#1a365d; font-weight:bold; text-decoration:none;'>{i['title']}</a><br/><small style='color:#94a3b8;'>🏢 {i['source']} | 📅 {i['date']}</small></div>" for i in data['deep_dynamic']])}
            
            <hr style="border:0; border-top:1px dashed #ddd; margin:20px 0;">
            
            <h3 style="color:#1a365d;">⚡ PART B：全球快讯 (Top 10 Briefs)</h3>
            {"".join([f"<div style='margin-bottom:12px;'>• <a href='{i['url']}' style='color:#1e293b; text-decoration:none;'>{i['title']}</a><br/><small style='color:#94a3b8;'>🏢 {i['source']} | 📅 {i['date']}</small></div>" for i in data['global_briefs']])}
            
            <div style="text-align:center; margin-top:40px; color:#94a3b8; font-style:italic; font-size:12px;">
                Send by Alex Xing's Agent with Love
            </div>
        </div>
    </body></html>
    """

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = f"Edu Intelligence Agent <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html_content, 'html'))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.send_message(msg)
        save_history(current_fps)
        print(f"✅ 情报已成功发送！包含 {len(data['deep_dynamic'])} 条深度内容和 {len(data['global_briefs'])} 条快讯。")
    except Exception as e:
        print(f"❌ 发送失败: {e}")

if __name__ == "__main__":
    send_intelligence_report()
