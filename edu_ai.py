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

def fetch_edu_news(days=7):
    # 扩大搜索范围，确保每个板块都有足够储备
    search_tasks = [
        {
            "id": "policy", 
            "name": "升学、政策与形势", 
            "icon": "🎓", 
            "color": "#2c5282", 
            "queries": [
                '("College board" OR NACAC OR UCAS OR "Common App") (News OR Admissions)',
                '("Open doors" OR "Quest bridge" OR "IIE") (Policy OR Enrollment)',
                '("International Education" OR "Higher Ed") (Policy OR Visa)'
            ]
        },
        {
            "id": "ai", 
            "name": "AI 与教学实践", 
            "icon": "🤖", 
            "color": "#4c51bf", 
            "queries": [
                '(AI OR ChatGPT OR "Generative AI") (Education OR HighSchool OR K12)',
                '("Artificial Intelligence") (Classroom OR Teaching OR Student)',
                '(AI OR "Large Language Model") (Assessment OR Academic Integrity)'
            ]
        },
        {
            "id": "market", 
            "name": "区域动态与行业洞察", 
            "icon": "🌏", 
            "color": "#2b6cb0", 
            "queries": [
                '("新学说" OR "顶思" OR "国际教育洞察")',
                '("Inside Higher Ed" OR "Times Higher Education") "International Education"',
                '("K12" OR "International School") (Global OR Market OR Trend)'
            ]
        }
    ]
    
    categorized_news = {"policy": [], "ai": [], "market": []}
    seen_urls = set()
    threshold = datetime.now() - timedelta(days=days)
    translator = GoogleTranslator(source='auto', target='zh-CN')

    print(f"开始深度检索：目标每个板块 15 条...")

    for task in search_tasks:
        task_results = []
        # 对每个板块下的多个子查询进行抓取
        for q in task["queries"]:
            if len(task_results) >= 15: break
            
            encoded_query = urllib.parse.quote(q)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(rss_url)
            
            for entry in feed.entries:
                if not hasattr(entry, 'published_parsed'): continue
                pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
                
                if pub_time > threshold and entry.link not in seen_urls:
                    seen_urls.add(entry.link)
                    task_results.append({
                        "title": entry.title,
                        "url": entry.link,
                        "source": entry.source.get('title', '教育动态'),
                        "date": pub_time.strftime('%m-%d'),
                        "timestamp": pub_time
                    })
                if len(task_results) >= 15: break
            time.sleep(0.5) # 微调停顿
        
        # 翻译该板块结果
        print(f" - 正在翻译【{task['name']}】板块...")
        for item in task_results:
            try:
                item["chi_title"] = translator.translate(item['title'])
            except:
                item["chi_title"] = item['title']
            categorized_news[task["id"]].append(item)
            
        print(f"✅ 【{task['name']}】抓取完成：{len(categorized_news[task['id']])} 条")

    return categorized_news

def format_section(title, icon, color, news_list):
    header = f"""
    <tr>
        <td style="padding: 18px 15px; background: {color}; font-weight: bold; color: #ffffff; font-size: 16px;">
            {icon} {title} (本周 {len(news_list)} 条)
        </td>
    </tr>"""
    
    if not news_list:
        return header + "<tr><td style='padding:15px; color:#999; background:#fff;'>本周暂无更新。</td></tr>"
    
    rows = ""
    for item in news_list:
        rows += f"""
        <tr>
            <td style="padding: 15px; border-bottom: 1px solid #edf2f7; background: #ffffff;">
                <div style="font-size: 15px; font-weight: bold; color: #2d3748; margin-bottom: 5px; line-height: 1.4;">{item['chi_title']}</div>
                <div style="font-size: 11px; color: #a0aec0; margin-bottom: 8px;">{item['title']}</div>
                <div style="font-size: 11px; color: #a0aec0;">
                    <span style="background:#f7fafc; color:{color}; padding:2px 5px; border-radius:3px; font-weight:bold;">{item['source']}</span> | {item['date']} 
                    | <a href="{item['url']}" style="color:{color}; text-decoration:none; font-weight: bold;">原文 →</a>
                </div>
            </td>
        </tr>"""
    return header + rows + "<tr><td style='height:15px; background:#f4f7f9;'></td></tr>"

def send_edu_email():
    sender = "alexanderxyh@gmail.com"
    password = os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com"]
    
    data = fetch_edu_news(days=7)
    
    policy_html = format_section("升学、政策与形势", "🎓", "#2c5282", data['policy'])
    ai_html = format_section("AI 与教学实践", "🤖", "#4c51bf", data['ai'])
    market_html = format_section("区域动态与行业洞察", "🌏", "#2b6cb0", data['market'])

    total_count = sum(len(v) for v in data.values())

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background:#f4f7f9; padding:10px;">
        <div style="max-width: 700px; margin: 0 auto; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 4px 15px rgba(0,0,0,0.1); border:1px solid #e2e8f0;">
            <div style="background:#1a365d; padding:30px 20px; text-align:center; color:#fff;">
                <h1 style="margin:0; font-size:22px;">全球教育 & AI 动态情报</h1>
                <p style="opacity:0.8; font-size:14px; margin-top:8px;">Agent速递：7天热点深度追踪</p>
                <div style="margin-top:12px; font-size:12px; background:rgba(255,255,255,0.15); display:inline-block; padding:4px 12px; border-radius:20px;">
                    今日情报总量：{total_count} 条精华
                </div>
            </div>
            <table style="width:100%; border-collapse:collapse;">
                {policy_html}
                {ai_html}
                {market_html}
            </table>
            <div style="padding:20px; text-align:center; font-size:11px; color:#a0aec0; background:#fcfcfc;">
                国家范围：美、英、加、澳、新、中、日、德、法<br>
                生成日期：{datetime.now().strftime('%Y-%m-%d')}
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['Subject'] = "Agent速递：全球7天AI与教育洞察"
    msg['From'] = f"Alex Edu Intel <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html_content, 'html'))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.send_message(msg)
    print(f"✅ 报告发送成功，共计 {total_count} 条动态。")

if __name__ == "__main__":
    send_edu_email()
