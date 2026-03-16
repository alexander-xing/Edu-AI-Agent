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

# --------------------------------------------------------------------------------
# 1. 精准化配置矩阵 (录取情报专项)
# --------------------------------------------------------------------------------

# 核心信源与域名加权
EDU_SOURCES = [
    'chronicle.com', 'insidehighered.com', 'thepienews.com', 'universityworldnews.com',
    'usnews.com/education', 'timeshighereducation.com', 'topuniversities.com',
    '.edu', 'moe.gov.cn', 'csc.edu.cn', 'britishcouncil.org'
]

# 严格黑名单：过滤体育、琐事、负面社会新闻
STRICT_BLACK_LIST = [
    'football', 'basketball', 'athletics', 'match', 'score', 'player', 'stadium',
    'obituary', 'alumni event', 'vaccine', 'patient', 'clinical', 'hiring', 'faculty',
    'shooting', 'protest', 'arrest'
]

# 意图触发词：标题必须包含以下核心词，确保与“录取/费用/政策”强相关
INTENT_KEYWORDS = [
    'admission', 'tuition', 'fee', 'deadline', 'policy', 'enrollment', 'requirement',
    'scholarship', 'visa', 'acceptance', 'criteria', 'standardized', 'test-optional',
    '录取', '学费', '招生', '截止', '政策', '雅思', '托福'
]

# --------------------------------------------------------------------------------
# 2. 深度情报抓取引擎
# --------------------------------------------------------------------------------

def fetch_edu_intelligence(days=30):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 正在从全球垂直源提取高价值情报...")
    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    results = {"policy": [], "deadlines": []}

    # 针对性搜索任务：利用高级搜索指令缩小范围
    tasks = [
        # 政策与中国留学生
        {"q": '(site:edu OR site:gov) "Chinese students" (admission OR policy OR enrollment)', "cat": "policy", "lang": "en"},
        # 录取标准与语言要求
        {"q": 'Top University (IELTS OR TOEFL OR SAT) requirement update 2026', "cat": "policy", "lang": "en"},
        # 学费与奖学金
        {"q": 'University "tuition fees" 2025 2026 increase international', "cat": "policy", "lang": "en"},
        # 申请截止日期
        {"q": 'Global University "application deadlines" 2025 2026', "cat": "deadlines", "lang": "en"},
        # 中文权威动态
        {"q": '名校 录取政策 2025 2026 (截止时间 OR 费用变动)', "cat": "policy", "lang": "zh-CN"}
    ]

    seen_urls = set()

    for task in tasks:
        # 模拟浏览器 User-Agent 增加抓取稳定性
        search_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(task['q'])}&hl={task['lang']}"
        feed = feedparser.parse(search_url)
        
        for entry in feed.entries:
            if entry.link in seen_urls: continue
            
            try:
                # 时间校验
                pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
                if pub_time < threshold: continue
            except: continue

            title_l = entry.title.lower()
            
            # --- 过滤层 1：排除黑名单 ---
            if any(b in title_l for b in STRICT_BLACK_LIST): continue
            
            # --- 过滤层 2：包含意图词 ---
            if not any(k in title_l for k in INTENT_KEYWORDS): continue
            
            # --- 过滤层 3：权威度筛选 (.edu 或特定白名单) ---
            is_edu = ".edu" in entry.link.lower()
            is_white = any(d in entry.link.lower() for d in EDU_SOURCES)
            if not (is_edu or is_white): continue

            # 执行翻译
            title = entry.title
            if task['lang'] != 'zh-CN':
                try: 
                    title = translator.translate(title)
                    time.sleep(0.5) # 避开翻译频率限制
                except: pass
            
            item = {
                "title": title,
                "source": entry.get('source', {}).get('title', '权威情报源'),
                "url": entry.link,
                "date": pub_time.strftime('%m-%d')
            }
            
            results[task['cat']].append(item)
            seen_urls.add(entry.link)
            
            # 每个类别最多取 20 条最相关的
            if len(results[task['cat']]) >= 20: break

    return results

# --------------------------------------------------------------------------------
# 3. 邮件发送引擎 (UI 优化版)
# --------------------------------------------------------------------------------

def send_intelligence_report():
    sender = "alexanderxyh@gmail.com"
    pw = os.environ.get('EMAIL_PASSWORD') 
    receivers = ["47697205@qq.com", "54517745@qq.com", "ying.xia@wlsafoundation.com"]
    
    if not pw:
        print("❌ 错误: 未检测到环境变量 EMAIL_PASSWORD")
        return

    data = fetch_edu_intelligence(days=30)
    subject = f"Ying大人：全球顶尖大学录取情报精选 ({datetime.now().strftime('%Y-%m-%d')})"
    
    def gen_list_html(items):
        if not items: return "<li style='color:#94a3b8; padding:10px;'>本周期内暂无符合筛选标准的新增内容</li>"
        li_html = ""
        for i in items:
            li_html += f"""
            <li style="margin-bottom:16px; border-bottom:1px solid #f1f5f9; padding-bottom:12px;">
                <a href="{i['url']}" style="color:#0f172a; text-decoration:none; font-weight:600; font-size:15px; display:block; margin-bottom:4px;">{i['title']}</a>
                <span style="color:#e11d48; font-size:12px; font-weight:700; background:#fff1f2; padding:2px 6px; border-radius:4px;">{i['source']}</span>
                <span style="color:#64748b; font-size:12px; margin-left:12px;">📅 {i['date']}</span>
            </li>
            """
        return li_html

    html_content = f"""
    <html><body style="font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, sans-serif; background:#f8fafc; padding:20px;">
        <div style="max-width:680px; margin:0 auto; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 10px 15px -3px rgba(0,0,0,0.1);">
            <div style="background:#e11d48; padding:30px 20px; text-align:center;">
                <h1 style="color:#ffffff; margin:0; font-size:22px; letter-spacing:1px;">全球顶尖大学录取情报周报</h1>
                <p style="color:#fda4af; margin-top:8px; font-size:14px;">录取政策 • 学费变动 • 申请截止窗口</p>
            </div>
            
            <div style="padding:30px;">
                <div style="margin-bottom:40px;">
                    <h3 style="color:#e11d48; font-size:16px; border-bottom:2px solid #fff1f2; padding-bottom:8px; margin-bottom:15px;">🏛️ 招生政策与学费情报 (Top 20)</h3>
                    <ul style="list-style:none; padding:0; margin:0;">{gen_list_html(data['policy'])}</ul>
                </div>
                
                <div>
                    <h3 style="color:#2563eb; font-size:16px; border-bottom:2px solid #eff6ff; padding-bottom:8px; margin-bottom:15px;">⏳ 申请截止与关键时间窗 (Top 20)</h3>
                    <ul style="list-style:none; padding:0; margin:0;">{gen_list_html(data['deadlines'])}</ul>
                </div>
            </div>
            
            <div style="background:#f1f5f9; padding:20px; text-align:center;">
                <p style="color:#94a3b8; font-size:12px; margin:0;">
                    基于 30 天全球垂直信源监控 | 频率：每周一推送<br>
                    Generated by Alex Xing's Agent
                </p>
            </div>
        </div>
    </body></html>
    """

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = f"Ying's Global Edu Agent <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html_content, 'html'))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.send_message(msg)
        print("✅ 报告已成功发送至收件箱！")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

# --------------------------------------------------------------------------------
# 4. 执行控制 (由 GitHub Action Cron 触发)
# --------------------------------------------------------------------------------

if __name__ == "__main__":
    send_intelligence_report()
