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
    """提取指纹用于去重：保留中文、英文字母和数字"""
    return "".join(re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]', title))[:40].lower()

def load_history():
    """读取过去已发送过的新闻指纹"""
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        # 只保留最近30天的记忆，防止文件无限增大
        return set(line.strip() for line in f.readlines())

def save_history(new_fps):
    """保存新发送的新闻指纹"""
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        for fp in new_fps:
            f.write(fp + "\n")

# --------------------------------------------------------------------------------
# 2. 垂直情报抓取核心 (更新为30天跨度)
# --------------------------------------------------------------------------------

def fetch_edu_intelligence(days=30): # 已更新为30天
    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    results = {
        "cn_policy": [], "cn_c9": [], "cn_highschool": [], "cn_ai_case": [],
        "intl_admission": [], "intl_ai_case": [], "intl_expert": []
    }
    
    # 核心：加载历史记忆
    sent_history = load_history()
    current_session_fps = set() 
    
    # --- 查询字典 (保持不变) ---
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
            
            # --- 去重逻辑升级 ---
            fp = get_fingerprint(entry.title)
            # 如果在历史记忆中，或者今天已经抓过了，就跳过
            if fp in sent_history or fp in current_session_fps:
                continue
            
            # 限制每个模块数量，保持邮件简洁
            if len(results[target_key]) >= 10: break 
            
            title = entry.title
            if lang != 'zh-CN':
                try: 
                    title = translator.translate(title)
                    time.sleep(0.3)
                except: pass
            
            current_session_fps.add(fp)
            results[target_key].append({
                "title": title,
                "source": entry.get('source', {}).get('title', '权威源'),
                "url": entry.link,
                "date": pub_time.strftime('%m-%d'),
                "fp": fp # 临时存储指纹
            })
        time.sleep(1)

    for k in cn_queries.keys(): process_feed(cn_queries, k, 'zh-CN', 'CN')
    for k in intl_queries.keys(): process_feed(intl_queries, k, 'en-US', 'US')
    
    # 将本轮抓取到的新指纹存入历史
    save_history(current_session_fps)
    
    return results

# --------------------------------------------------------------------------------
# 3. 邮件发送模块 (更新标题与描述)
# --------------------------------------------------------------------------------

def send_intelligence_report():
    sender, pw = "alexanderxyh@gmail.com", os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com", "ying.xia@wlsafoundation.com"]
    
    print("🛰️ 正在精准抓取 30 天内垂直模块（已开启跨天去重模式）...")
    data = fetch_edu_intelligence(days=30)
    
    # 检查是否有新内容，如果没有，可以选则不发邮件，避免打扰
    total_items = sum(len(v) for v in data.values())
    if total_items == 0:
        print("📭 今日无新增情报，跳过邮件发送。")
        return

    from __main__ import format_html_refined # 引用排版函数
    content_rows = format_html_refined(data)
    
    # 底部爱心 HTML (保持原样)
    heart_html = """<div style="text-align: center; margin-top: 40px;"><div style="display: inline-block; position: relative; width: 50px; height: 45px;"><div style="position: absolute; width: 25px; height: 40px; background: #f43f5e; border-radius: 50px 50px 0 0; transform: rotate(-45deg); left: 13px; transform-origin: 0 100%;"></div><div style="position: absolute; width: 25px; height: 40px; background: #f43f5e; border-radius: 50px 50px 0 0; transform: rotate(45deg); left: -12px; transform-origin: 100% 100%;"></div></div></div>"""

    # 更新邮件标题为您的最新指令
    subject = f"Ying大人的'垂直教育情报每日滚动刷新'：30天全球深度精华版 (10+10)"
    
    email_template = f"""
    <html><body style="font-family:'PingFang SC',sans-serif; background:#f4f7f9; padding:20px;">
        <div style="max-width:700px; margin:0 auto;">
            <div style="text-align:center; padding-bottom:20px;">
                <h2 style="color:#1e293b; margin:0;">{subject}</h2>
                <p style="font-size:12px; color:#64748b; margin-top:5px;">跨天去重模式 | 抓取范围：30天 | 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            </div>
            <table style="width:100%; border-collapse:collapse;">{content_rows}</table>
            {heart_html}
            <div style="padding:10px 30px 40px 30px; text-align:center; font-size:11px; color:#94a3b8; line-height:1.6;">
                <p style="margin:0; font-weight:bold; color:#64748b;">献给 XIA YING 女士</p>
                本报告由 XING YINGHUA 先生定制的教育 Agent 生成<br>
                记忆库：sent_history.txt | 30天全量扫描
            </div>
        </div>
    </body></html>"""

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = f"Edu Intelligence Agent <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(email_template, 'html'))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.send_message(msg)
        print(f"✅ 报告已成功刷新。今日新增 {total_items} 条情报。")
    except Exception as e:
        print(f"❌ 失败: {e}")

# (注：format_html_refined 函数请保留您原代码中的逻辑)
