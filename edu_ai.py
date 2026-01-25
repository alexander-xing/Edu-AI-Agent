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
# 1. 核心白名单与过滤配置
# --------------------------------------------------------------------------------

EDU_DOMAINS = [
    'jyb.cn', 'eol.cn', 'jiemodui.com', 'djchina.com', 'moe.gov.cn', 'shanghairanking.cn',
    'lanjing.com', 'xiaozhangbang.com', '36kr.com', 'caixin.com', 'people.com.cn',
    'chronicle.com', 'insidehighered.com', 'timeshighereducation.com', 'thepienews.com',
    'edsurge.com', 'edweek.org', 'hechingerreport.org', 'universityworldnews.com',
    'harvard.edu', 'stanford.edu', 'mit.edu', 'ox.ac.uk', 'cam.ac.uk', 'nature.com'
]

# 必须排除的医疗/社会噪音
BLACK_LIST = ['疫苗', '患者', '临床', '病毒', 'vaccine', 'patient', 'clinical', 'surgery']

# --------------------------------------------------------------------------------
# 2. 抓取引擎 (10+10)
# --------------------------------------------------------------------------------

def fetch_edu_intelligence(days=30):
    print("开始从 Google News 检索情报...")
    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    results = {"deep": [], "briefs": []}
    
    # 任务列表
    tasks = [
        {"q": "教育政策 OR AI教学 OR 招生录取", "lang": "zh-CN", "gl": "CN", "cat": "deep"},
        {"q": "Higher Education Strategy OR AI in Classroom", "lang": "en", "gl": "US", "cat": "deep"},
        {"q": "University World News OR Global Admissions", "lang": "en", "gl": "US", "cat": "briefs"}
    ]

    for task in tasks:
        print(f"正在抓取类别: {task['cat']} (Query: {task['q']})")
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(task['q'])}&hl={task['lang']}&gl={task['gl']}"
        feed = feedparser.parse(url)
        
        if not feed.entries:
            print(f"警告: 检索式 {task['q']} 未抓取到内容，请检查网络（需代理）。")

        for entry in feed.entries:
            # 1. 时间过滤
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold: continue
            
            # 2. 噪音过滤
            if any(b in entry.title.lower() for b in BLACK_LIST): continue
            
            # 3. 垂直度校准：白名单优先，或包含教育核心词
            is_edu = any(d in entry.link.lower() for d in EDU_DOMAINS) or \
                     any(k in entry.title for k in ['教育', '学校', '招生', '学科', 'University', 'Education'])
            
            if not is_edu: continue
            if len(results[task['cat']]) >= 10: break

            # 4. 翻译处理
            title = entry.title
            if task['lang'] != 'zh-CN':
                try: 
                    title = translator.translate(title)
                    time.sleep(0.2)
                except: pass
            
            results[task['cat']].append({
                "title": title,
                "source": entry.get('source', {}).get('title', '权威源'),
                "url": entry.link,
                "date": pub_time.strftime('%m-%d')
            })
            
    return results

# --------------------------------------------------------------------------------
# 3. 邮件构造与强制发送 (移除日期锁与去重记录)
# --------------------------------------------------------------------------------

def send_test_report():
    # --- 账号配置 ---
    # 建议测试时直接在这里填入 16 位应用专用密码，或确保环境变量已生效
    sender = "alexanderxyh@gmail.com"
    pw = os.environ.get('EMAIL_PASSWORD') 
    receivers = ["47697205@qq.com", "54517745@qq.com", "ying.xia@wlsafoundation.com"]
    
    if not pw:
        print("错误: 未检测到 EMAIL_PASSWORD 环境变量。")
        return

    # 1. 抓取数据
    data = fetch_edu_intelligence(days=30)
    total_count = len(data['deep']) + len(data['briefs'])
    print(f"抓取完成，共计 {total_count} 条高质量情报。")

    if total_count == 0:
        print("未抓取到符合过滤条件的内容，邮件不予发送。")
        return

    # 2. 邮件标题 (Ying大人专属)
    subject = "Ying大人的'垂直教育情报每日滚动刷新'：30天全球深度精华版 (10+10)"
    
    # 3. HTML 构造
    html_items_a = "".join([f"<li style='margin-bottom:10px;'><a href='{i['url']}' style='color:#c02424; font-weight:bold; text-decoration:none;'>{i['title']}</a><br><small style='color:#666;'>🏢 {i['source']} | 📅 {i['date']}</small></li>" for i in data['deep']])
    html_items_b = "".join([f"<li style='margin-bottom:10px;'><a href='{i['url']}' style='color:#1a365d; text-decoration:none;'>{i['title']}</a><br><small style='color:#666;'>🏢 {i['source']} | 📅 {i['date']}</small></li>" for i in data['briefs']])

    email_content = f"""
    <html><body style="font-family:sans-serif; color:#333;">
        <div style="max-width:700px; margin:0 auto; border:1px solid #eee; padding:20px; border-radius:15px;">
            <h2 style="color:#c02424; text-align:center; border-bottom:2px solid #c02424; padding-bottom:10px;">{subject}</h2>
            <p style="text-align:center; font-size:12px; color:#999;">测试模式：已关闭日期锁与历史去重 | {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            
            <h3 style="background:#fdf2f2; padding:10px; color:#c02424; border-radius:5px;">🛡️ PART A: 深度动态 (Top 10)</h3>
            <ul>{html_items_a if html_items_a else "<li>暂无满足条件内容</li>"}</ul>
            
            <h3 style="background:#f4f7fa; padding:10px; color:#1a365d; border-radius:5px;">⚡ PART B: 全球快讯 (Top 10)</h3>
            <ul>{html_items_b if html_items_b else "<li>暂无满足条件内容</li>"}</ul>
            
            <div style="text-align:center; margin-top:30px; font-size:11px; color:#94a3b8;">
                Send by Alex Xing's Agent with Love
            </div>
        </div>
    </body></html>
    """

    # 4. 执行 SMTP 发送
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = f"Edu Intelligence Agent <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(email_content, 'html'))

    try:
        print(f"正在连接 Gmail 服务器并发往 {receivers}...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.send_message(msg)
        print("✅ 邮件已成功送达！请检查收件箱（以及垃圾邮件箱）。")
    except Exception as e:
        print(f"❌ 发送失败，错误原因: {e}")

if __name__ == "__main__":
    send_test_report()
