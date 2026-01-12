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
# 1. 核心配置：精准分模块检索指令
# --------------------------------------------------------------------------------

def fetch_edu_intelligence(days=14):
    translator = GoogleTranslator(source='auto', target='zh-CN')
    threshold = datetime.now() - timedelta(days=days)
    results = {
        "cn_policy": [], "cn_c9": [], "cn_highschool": [], "cn_ai_case": [],
        "intl_admission": [], "intl_ai_case": [], "intl_expert": []
    }
    
    # 用于全局去重
    seen_titles = set()

    # --- 中国部分：4个子模块 ---
    cn_queries = {
        "cn_policy": '(教育部 OR 国务院) (教育政策 OR 评价改革 OR 十五五规划) OR "教育家" (未来教育 OR 洞察)',
        "cn_c9": '(清华 OR 北大 OR 浙大 OR 复旦 OR 上海交大 OR 南大 OR 中科大 OR 西交 OR 哈工大) (招生政策 OR AI专业 OR 录取 OR 学科建设)',
        "cn_highschool": '(人大附 OR 北京四中 OR 上海平和 OR 包玉刚 OR 深国交 OR 杭外 OR 南外 OR WLSA) (升学榜单 OR 招生简章 OR 开放日)',
        "cn_ai_case": '(中学 OR 初中 OR 高中) (AI教学 OR 智慧课堂 OR 数字化转型 OR 人工智能通识课) 案例'
    }

    # --- 国际部分：3个子模块 (强化排除逻辑版) ---
    intl_queries = {
        # 维度 1：锁定招生办政策，排除医疗、健康、疫苗、临床等干扰
        "intl_admission": 'site:edu (Admissions OR "Entry Requirements") ("Chinese students" OR "International students") "2026" -clinical -medical -vaccine -health',
        
        # 维度 2：锁定教学实践，排除纯技术研发或生物医疗 AI
        "intl_ai_case": '(site:edsurge.com OR site:chronicle.com OR site:edweek.org) "Generative AI" (Classroom OR Curriculum OR "Teaching Practice") -oncology -biotech -protein',
        
        # 维度 3：锁定教育趋势，排除护理、流行病学等非教育类专家观点
        "intl_expert": 'site:edu ("Future of Higher Education" OR "Educational Trends") (Professor OR Dean OR Provost) -nursing -epidemiology -surgery'
    }

    def process_feed(queries, target_key, lang='zh-CN', gl='CN'):
        for key, q in queries.items():
            if key != target_key: continue
            # Google News RSS 接口
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl={lang}&gl={gl}"
            feed = feedparser.parse(url)
            
            for entry in feed.entries:
                if not hasattr(entry, 'published_parsed'): continue
                pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
                if pub_time < threshold: continue
                
                # 模块限额 5 条
                if len(results[key]) >= 5: break
                
                # 基础去重逻辑
                clean_title = re.sub(r'[^\w]', '', entry.title)
                if clean_title in seen_titles: continue
                seen_titles.add(clean_title)
                
                title = entry.title
                # 国际内容翻译
                if lang != 'zh-CN':
                    try: 
                        title = translator.translate(title)
                        time.sleep(0.3) # 避免翻译过快被封
                    except: pass
                
                results[key].append({
                    "title": title,
                    "source": entry.source.get('title', '权威来源') if hasattr(entry, 'source') else '教育官网',
                    "url": entry.link,
                    "date": pub_time.strftime('%m-%d')
                })
            time.sleep(1) # 频率限制

    # 执行抓取
    for k in cn_queries.keys(): process_feed(cn_queries, k, 'zh-CN', 'CN')
    for k in intl_queries.keys(): process_feed(intl_queries, k, 'en-US', 'US')
    
    return results

# --------------------------------------------------------------------------------
# 2. 邮件美化模版 (保持原有结构)
# --------------------------------------------------------------------------------

def format_html(data):
    html = ""
    mapping = [
        ("cn_policy", "🏛️ 1. 国家政策与教育家洞察", "#c02424"),
        ("cn_c9", "🎓 2. C9名校招生与专业动态", "#c02424"),
        ("cn_highschool", "🏫 3. 五大城市一梯队国高动态", "#c02424"),
        ("cn_ai_case", "🤖 4. 国内高中/初中AI教学实践", "#c02424"),
        ("intl_admission", "🌍 1. 全球Top 50大学招生政策", "#1a365d"),
        ("intl_ai_case", "💡 2. 海外大学或高中AI教学案例", "#1a365d"),
        ("intl_expert", "🔭 3. 国际教育趋势与专家观点", "#1a365d")
    ]
    
    for key, label, color in mapping:
        if key == "cn_policy": 
            html += f'<tr><td style="padding:15px; background:#f8fafc; border-left:6px solid {color}; font-size:18px; font-weight:bold; color:{color};">第一部分：中国教育洞察</td></tr>'
        if key == "intl_admission":
            html += f'<tr><td style="padding:15px; background:#f8fafc; border-left:6px solid {color}; font-size:18px; font-weight:bold; color:{color};">第二部分：国外教育洞察</td></tr>'
        
        html += f'<tr><td style="padding:8px 15px; font-size:14px; font-weight:bold; color:#475569; background:#f1f5f9;">{label}</td></tr>'
        
        items = data.get(key, [])
        if not items:
            html += '<tr><td style="padding:10px 15px; font-size:13px; color:#94a3b8; background:#fff;">本期暂无更新</td></tr>'
        else:
            for item in items:
                html += f"""
                <tr><td style="padding:12px 15px; border-bottom:1px solid #f1f5f9; background:#fff;">
                    <a href="{item['url']}" style="text-decoration:none; color:#1e293b; font-size:14px; font-weight:500;">{item['title']}</a>
                    <div style="font-size:11px; color:#94a3b8; margin-top:5px;">🏢 {item['source']} | 📅 {item['date']}</div>
                </td></tr>"""
    return html

def send_intelligence_report():
    sender = "alexanderxyh@gmail.com"
    pw = os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com"]
    
    if not pw:
        print("❌ 错误：未发现 EMAIL_PASSWORD 环境变量")
        return

    data = fetch_edu_intelligence(days=14)
    content_rows = format_html(data)
    
    email_template = f"""
    <html><body style="font-family:'PingFang SC',Arial,sans-serif; background:#f4f7f9; padding:20px;">
        <div style="max-width:750px; margin:0 auto; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 10px 25px rgba(0,0,0,0.05);">
            <div style="background:#1e293b; padding:35px; text-align:center; color:#fff;">
                <h1 style="margin:0; font-size:24px; letter-spacing:1px;">Ying大人的"垂直教育情报每日滚动刷新"</h1>
                <p style="font-size:14px; opacity:0.8; margin-top:10px;">14天全球深度精华版 (7大垂直模块)</p>
            </div>
            <table style="width:100%; border-collapse:collapse;">{content_rows}</table>
            <div style="padding:20px; background:#f8fafc; font-size:11px; color:#94a3b8; text-align:center;">
                监控范围：京沪深杭宁名校、C9联盟、Top 50名校官网、垂直AI教育源
            </div>
        </div>
    </body></html>"""

    msg = MIMEMultipart()
    msg['Subject'] = f"Ying大人的'垂直教育情报每日滚动刷新'：30天全球深度精华版 (10+10) ({datetime.now().strftime('%m/%d')})"
    msg['From'] = f"Edu Intelligence Agent <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(email_template, 'html'))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, pw)
            server.send_message(msg)
        print("🚀 细化版重构报告已成功发送至目标邮箱。")
    except Exception as e:
        print(f"❌ 发送失败: {e}")

if __name__ == "__main__":
    send_intelligence_report()
