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
# 1. 垂直源与过滤协议
# --------------------------------------------------------------------------------

# 核心 50 个白名单域名
WHITELIST_DOMAINS = [
    'jyb.cn', 'eol.cn', 'jiemodui.com', 'djchina.com', 'moe.gov.cn', 'shanghairanking.cn',
    'chronicle.com', 'insidehighered.com', 'timeshighereducation.com', 'thepienews.com',
    'edsurge.com', 'edweek.org', 'hechingerreport.org', 'universityworldnews.com',
    'harvard.edu', 'stanford.edu', 'mit.edu', 'ox.ac.uk', 'cam.ac.uk', 'nature.com',
    'lanjing.com', 'xiaozhangbang.com', '36kr.com', 'caixin.com', 'people.com.cn'
]

# 严格黑名单
BLACK_LIST = ['疫苗', '临床', '患者', '手术', '病毒', 'vaccine', 'patient', 'clinical', 'surgery']

# --------------------------------------------------------------------------------
# 2. 增强型抓取逻辑
# --------------------------------------------------------------------------------

def fetch_edu_intelligence(days=30):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 启动 10+10 情报抓取引擎...")
    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    results = {"deep": [], "briefs": []}

    # 任务分层逻辑
    tasks = [
        # Part A: 深度与政策 (锁定权威源词汇)
        {"q": "教育政策 OR 十五五规划 OR 学科建设 OR AI教学", "lang": "zh-CN", "gl": "CN", "cat": "deep"},
        {"q": "Higher Education Strategy OR AI Policy in University", "lang": "en", "gl": "US", "cat": "deep"},
        
        # Part B: 全球动态与快讯 (增加关键词多样性，防止结果为空)
        {"q": "Global University Admissions OR International Students news", "lang": "en", "gl": "US", "cat": "briefs"},
        {"q": "EdTech trends OR Campus Technology OR Higher Ed Dive", "lang": "en", "gl": "US", "cat": "briefs"},
        {"q": "大学招生 OR 留学动态 OR 国际教育资讯", "lang": "zh-CN", "gl": "CN", "cat": "briefs"}
    ]

    for task in tasks:
        print(f"-> 正在检索: {task['q']} ({task['lang']})")
        search_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(task['q'])}&hl={task['lang']}&gl={task['gl']}"
        feed = feedparser.parse(search_url)
        
        raw_count = len(feed.entries)
        valid_in_task = 0

        for entry in feed.entries:
            # 1. 基础时间过滤
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold: continue
            
            # 2. 医疗/杂讯过滤
            title_l = entry.title.lower()
            if any(b in title_l for b in BLACK_LIST): continue
            
            # 3. 垂直度放行逻辑
            # 条件：来自白名单域名 OR 链接包含 .edu OR 标题包含核心教育词汇
            is_edu = any(d in entry.link.lower() for d in WHITELIST_DOMAINS) or \
                     ".edu" in entry.link.lower() or \
                     any(k in entry.title for k in ['招生', '学科', '录取', 'Education', 'University', 'Admissions'])

            if not is_edu: continue
            if len(results[task['cat']]) >= 10: break

            # 4. 翻译与格式化
            title = entry.title
            if task['lang'] != 'zh-CN':
                try: 
                    title = translator.translate(title)
                    time.sleep(0.2)
                except: pass
            
            results[task['cat']].append({
                "title": title,
                "source": entry.get('source', {}).get('title', '垂直信源'),
                "url": entry.link,
                "date": pub_time.strftime('%m-%d')
            })
            valid_in_task += 1
        
        print(f"   [状态] 原始抓取: {raw_count} | 过滤后留存: {valid_in_task}")

    return results

# --------------------------------------------------------------------------------
# 3. 邮件发送引擎 (已移除日期锁)
# --------------------------------------------------------------------------------

def send_intelligence_report():
    # --- 账号配置 ---
    sender = "alexanderxyh@gmail.com"
    pw = os.environ.get('EMAIL_PASSWORD') # 也可以临时直接填入16位应用密码进行测试
    receivers = ["47697205@qq.com", "54517745@qq.com", "ying.xia@wlsafoundation.com"]
    
    if not pw:
        print("❌ 错误: 未找到 EMAIL_PASSWORD。请执行 export EMAIL_PASSWORD='你的密码'")
        return

    # 抓取数据
    data = fetch_edu_intelligence(days=30)
    
    # 构造邮件标题
    subject = "Ying大人的\"垂直教育情报每日滚动刷新\"：30天全球深度精华版 (10+10)"
    
    # 构建 HTML 列表
    def gen_list(items):
        if not items: return "<li style='color:#999;'>今日该分类暂无更新</li>"
        li_html = ""
        for i in items:
            li_html += f"""
            <li style="margin-bottom:12px; border-bottom:1px solid #eee; padding-bottom:8px;">
                <a href="{i['url']}" style="color:#1a365d; text-decoration:none; font-weight:bold; font-size:14px;">{i['title']}</a><br>
                <span style="color:#666; font-size:12px;">🏢 {i['source']} | 📅 {i['date']}</span>
            </li>
            """
        return li_html

    html_content = f"""
    <html><body style="font-family:'PingFang SC', sans-serif; background:#f4f7f9; padding:20px;">
        <div style="max-width:700px; margin:0 auto; background:#fff; padding:25px; border-radius:15px; border:1px solid #e1e4e8;">
            <h2 style="color:#c02424; text-align:center; margin-bottom:5px;">{subject}</h2>
            <p style="text-align:center; font-size:12px; color:#999; margin-bottom:25px;">
                测试模式：日期锁已禁用 | 周期：30天深度覆盖 | 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
            </p>
            
            <div style="background:#fdf2f2; padding:15px; border-radius:10px; margin-bottom:20px;">
                <h3 style="color:#c02424; margin-top:0; border-left:4px solid #c02424; padding-left:10px;">🏛️ PART A: 深度动态 (Top 10)</h3>
                <ul style="list-style:none; padding-left:0;">{gen_list(data['deep'])}</ul>
            </div>
            
            <div style="background:#f4f7fa; padding:15px; border-radius:10px;">
                <h3 style="color:#1a365d; margin-top:0; border-left:4px solid #1a365d; padding-left:10px;">⚡ PART B: 全球快讯 (Top 10)</h3>
                <ul style="list-style:none; padding-left:0;">{gen_list(data['briefs'])}</ul>
            </div>
            
            <div style="text-align:center; margin-top:40px;">
                <div style="color:#f43f5e; font-size:24px;">♥</div>
                <div style="color:#94a3b8; font-size:12px; font-style:italic;">Send by Alex Xing's Agent with Love</div>
            </div>
        </div>
    </body></html>
    """

    # 执行发送
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = f"Ying's Edu Agent <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html_content, 'html'))

    try:
        print(f"正在建立安全连接并发送至 {receivers}...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.send_message(msg)
        print("✅ 任务圆满完成，邮件已送达。")
    except Exception as e:
        print(f"❌ 发送过程出错: {e}")

if __name__ == "__main__":
    send_intelligence_report()
