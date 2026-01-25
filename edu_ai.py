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
# 1. 垂直源协议：全球教育白名单 Top 100 (涵盖名校、政府、垂直媒体)
# --------------------------------------------------------------------------------

WHITELIST_DOMAINS = [
    # --- 中国权威/垂直 (30) ---
    'moe.gov.cn', 'jyb.cn', 'eol.cn', 'jiemodui.com', 'djchina.com', 'shanghairanking.cn',
    'lanjing.com', 'xiaozhangbang.com', '36kr.com', 'caixin.com', 'people.com.cn', 'xinhuanet.com',
    'edu.sina.com.cn', 'edu.qq.com', 'edu.163.com', 'sohu.com', 'thepaper.cn', 'bjnews.com.cn',
    'gmw.cn', 'rmzb.com.cn', 'zhibo8.cc', 'douban.com', 'zhihu.com', 'huxiu.com',
    'tsinghua.edu.cn', 'pku.edu.cn', 'fudan.edu.cn', 'zju.edu.cn', 'sjtu.edu.cn', 'ustc.edu.cn',
    
    # --- 国际教育垂直媒体/组织 (30) ---
    'chronicle.com', 'insidehighered.com', 'timeshighereducation.com', 'thepienews.com',
    'edsurge.com', 'edweek.org', 'hechingerreport.org', 'universityworldnews.com',
    'campustechnology.com', 'highereddive.com', 'k12dive.com', 'edsource.org',
    'educationnext.org', 'chalkbeat.org', 'thejournal.com', 'smartbrief.com',
    'worldbank.org', 'unesco.org', 'oecd.org', 'britishcouncil.org', 'collegeboard.org',
    'ets.org', 'qs.com', 'topuniversities.com', 'usnews.com', 'forbes.com', 
    'economist.com', 'nature.com', 'science.org', 'scientificamerican.com',

    # --- 国际顶尖大学官网 (40) ---
    'harvard.edu', 'stanford.edu', 'mit.edu', 'ox.ac.uk', 'cam.ac.uk', 'caltech.edu',
    'princeton.edu', 'yale.edu', 'columbia.edu', 'uchicago.edu', 'upenn.edu', 'jhu.edu',
    'berkeley.edu', 'cornell.edu', 'ucla.edu', 'ethz.ch', 'ucl.ac.uk', 'imperial.ac.uk',
    'nus.edu.sg', 'hku.hk', 'utoronto.ca', 'unimelb.edu.au', 'nyu.edu', 'duke.edu',
    'northwestern.edu', 'brown.edu', 'cmu.edu', 'dartmouth.edu', 'vanderbilt.edu',
    'rice.edu', 'wustl.edu', 'emory.edu', 'nd.edu', 'georgetown.edu', 'umich.edu',
    'usc.edu', 'virginia.edu', 'gatech.edu', 'lse.ac.uk', 'kcl.ac.uk'
]

# 严格黑名单：过滤非教育类的医疗、社会负面等噪音
BLACK_LIST = ['疫苗', '临床', '患者', '手术', '病毒', '接种', 'vaccine', 'patient', 'clinical', 'surgery', 'outbreak']

# --------------------------------------------------------------------------------
# 2. 增强型抓取逻辑 (20+20)
# --------------------------------------------------------------------------------

def fetch_edu_intelligence(days=30):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 启动 20+20 深度情报抓取引擎...")
    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    results = {"deep": [], "briefs": []}

    # 任务列表：通过多个关键词组合确保 Part B 能够填满 20 条
    tasks = [
        # Part A: 深度与政策
        {"q": "教育政策 OR 十五五规划 OR 学科建设 OR AI教学实践", "lang": "zh-CN", "gl": "CN", "cat": "deep"},
        {"q": "Higher Education Strategy OR AI Curriculum Reform OR Provost", "lang": "en", "gl": "US", "cat": "deep"},
        
        # Part B: 全球动态与快讯
        {"q": "Global University Admissions OR International Students OR Study Abroad", "lang": "en", "gl": "US", "cat": "briefs"},
        {"q": "EdTech Innovation OR University Ranking OR Campus News", "lang": "en", "gl": "US", "cat": "briefs"},
        {"q": "大学招生动态 OR 留学资讯 OR 国际化办学", "lang": "zh-CN", "gl": "CN", "cat": "briefs"}
    ]

    for task in tasks:
        print(f"-> 正在检索: {task['q']} ({task['lang']})")
        search_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(task['q'])}&hl={task['lang']}&gl={task['gl']}"
        feed = feedparser.parse(search_url)
        
        valid_in_task = 0
        for entry in feed.entries:
            # 1. 时间过滤
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            if pub_time < threshold: continue
            
            # 2. 杂讯过滤
            title_l = entry.title.lower()
            if any(b in title_l for b in BLACK_LIST): continue
            
            # 3. 垂直度校验 (白名单域名匹配 或 教育核心词)
            is_edu = any(d in entry.link.lower() for d in WHITELIST_DOMAINS) or \
                     ".edu" in entry.link.lower() or \
                     any(k in entry.title for k in ['招生', '学科', '课程', 'Education', 'University', 'Student'])

            if not is_edu: continue
            
            # 检查去重 (按标题指纹)
            if len(results[task['cat']]) >= 20: break

            # 4. 翻译
            title = entry.title
            if task['lang'] != 'zh-CN':
                try: 
                    title = translator.translate(title)
                    time.sleep(0.3) # 稍微增加延迟，保护翻译接口
                except: pass
            
            results[task['cat']].append({
                "title": title,
                "source": entry.get('source', {}).get('title', '垂直信源'),
                "url": entry.link,
                "date": pub_time.strftime('%m-%d')
            })
            valid_in_task += 1
        
        print(f"   [状态] 类别 {task['cat']} 当前累计: {len(results[task['cat']])}")

    return results

# --------------------------------------------------------------------------------
# 3. 邮件发送引擎
# --------------------------------------------------------------------------------

def send_intelligence_report():
    # --- 账号配置 ---
    sender = "alexanderxyh@gmail.com"
    pw = os.environ.get('EMAIL_PASSWORD') 
    receivers = ["47697205@qq.com", "54517745@qq.com", "ying.xia@wlsafoundation.com"]
    
    if not pw:
        print("❌ 错误: 未找到 EMAIL_PASSWORD 环境参数。")
        return

    # 抓取数据
    data = fetch_edu_intelligence(days=30)
    
    # 构造邮件标题 (已更新为 20+20)
    subject = "Ying大人的\"垂直教育情报每日滚动刷新\"：30天全球深度精华版 (20+20)"
    
    def gen_list(items):
        if not items: return "<li style='color:#999;'>今日该分类暂无更新内容</li>"
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
        <div style="max-width:750px; margin:0 auto; background:#fff; padding:30px; border-radius:15px; border:1px solid #e1e4e8;">
            <h2 style="color:#c02424; text-align:center; margin-bottom:5px;">{subject}</h2>
            <p style="text-align:center; font-size:12px; color:#999; margin-bottom:25px;">
                监测范围：Top 100 全球垂直源 | 周期：30天 | 状态：测试模式(去重已关) | {datetime.now().strftime('%Y-%m-%d %H:%M')}
            </p>
            
            <div style="background:#fdf2f2; padding:15px; border-radius:10px; margin-bottom:25px; border:1px solid #fbdada;">
                <h3 style="color:#c02424; margin-top:0; border-left:4px solid #c02424; padding-left:10px;">🏛️ PART A: 深度动态 (Top 20)</h3>
                <ul style="list-style:none; padding-left:0;">{gen_list(data['deep'])}</ul>
            </div>
            
            <div style="background:#f4f7fa; padding:15px; border-radius:10px; border:1px solid #dbeafe;">
                <h3 style="color:#1a365d; margin-top:0; border-left:4px solid #1a365d; padding-left:10px;">⚡ PART B: 全球快讯 (Top 20)</h3>
                <ul style="list-style:none; padding-left:0;">{gen_list(data['briefs'])}</ul>
            </div>
            
            <div style="text-align:center; margin-top:40px;">
                <div style="color:#f43f5e; font-size:20px;">♥</div>
                <div style="color:#94a3b8; font-size:12px; font-style:italic;">Send by Alex Xing's Agent with Love</div>
            </div>
        </div>
    </body></html>
    """

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = f"Ying's Edu Agent <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html_content, 'html'))

    try:
        print(f"正在通过加密通道发送至 {receivers}...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.send_message(msg)
        print("✅ 20+20 报告发送成功！")
    except Exception as e:
        print(f"❌ 发送失败: {e}")

if __name__ == "__main__":
    send_intelligence_report()
