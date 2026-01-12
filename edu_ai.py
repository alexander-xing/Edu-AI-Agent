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
    # 定义搜索矩阵
    queries = {
        "policy": '("College board" OR "Quest bridge" OR NACAC OR "Open doors" OR UCAS OR "Common App") (Policy OR Admissions OR Enrollment OR SAT OR AP OR IB OR "A-Level")',
        "ai": '(AI OR "Generative AI" OR ChatGPT OR "Artificial Intelligence") (Education OR "High School" OR K12 OR Classroom OR Assessment)',
        "market": '("新学说" OR "顶思" OR "国际教育洞察" OR "Inside Higher Ed" OR "Chronicle of Higher Ed") ("International Education" OR "Global Trends" OR "Study Abroad")'
    }
    
    # 汇总所有结果
    raw_results = []
    seen_urls = set()
    threshold = datetime.now() - timedelta(days=days)
    translator = GoogleTranslator(source='auto', target='zh-CN')

    print(f"正在深度扫描过去 {days} 天的全球教育动态...")

    for category, q in queries.items():
        encoded_query = urllib.parse.quote(q)
        # 增加 ceid 和 hl 权重，确保获取全球热度最高的英文和中文资讯
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed'): continue
            pub_time = datetime.fromtimestamp(mktime(entry.published_parsed))
            
            if pub_time > threshold and entry.link not in seen_urls:
                seen_urls.add(entry.link)
                raw_results.append({
                    "category": category,
                    "title": entry.title,
                    "url": entry.link,
                    "source": entry.source.get('title', '教育动态'),
                    "date_obj": pub_time,
                    "date": pub_time.strftime('%m-%d')
                })
        time.sleep(1)

    # 按照时间降序排序（确保最新最热）
    raw_results.sort(key=lambda x: x['date_obj'], reverse=True)

    # 取前25条（预防翻译失败或其他损耗，确保最终不少于20条）
    final_list = raw_results[:25]
    
    # 分类打包
    categorized_news = {"policy": [], "ai": [], "market": []}
    for item in final_list:
        try:
            # 执行翻译
            item["chi_title"] = translator.translate(item['title'])
        except:
            item["chi_title"] = item['title']
        
        categorized_news[item['category']].append(item)
        
    return categorized_news

def format_section(title, icon, color, news_list):
    if not news_list:
        return ""
    
    header = f"""
    <tr>
        <td style="padding: 18px 15px; background: {color}; font-weight: bold; color: #ffffff; font-size: 16px; border-radius: 4px 4px 0 0;">
            {icon} {title}
        </td>
    </tr>"""
    
    rows = ""
    for item in news_list:
        rows += f"""
        <tr>
            <td style="padding: 15px; border-bottom: 1px solid #edf2f7; background: #ffffff;">
                <div style="font-size: 15px; font-weight: bold; color: #2d3748; margin-bottom: 4px; line-height: 1.4;">{item['chi_title']}</div>
                <div style="font-size: 11px; color: #a0aec0; margin-bottom: 8px;">{item['title']}</div>
                <div style="font-size: 11px; color: #a0aec0; display: flex; justify-content: space-between;">
                    <span><b>{item['source']}</b> | {item['date']}</span>
                    <a href="{item['url']}" style="color:{color}; text-decoration:none; font-weight: bold;">查看原文 →</a>
                </div>
            </td>
        </tr>"""
    return header + rows + "<tr><td style='height:15px;'></td></tr>"

def send_edu_email():
    sender = "alexanderxyh@gmail.com"
    password = os.environ.get('EMAIL_PASSWORD')
    receivers = ["47697205@qq.com", "54517745@qq.com"]
    
    categorized_data = fetch_edu_news(days=7)
    
    # 构建三大板块
    policy_html = format_section("升学、政策与形势", "🎓", "#2c5282", categorized_data['policy'])
    ai_html = format_section("AI 与教学实践", "🤖", "#4c51bf", categorized_data['ai'])
    market_html = format_section("区域动态与行业洞察", "🌏", "#2b6cb0", categorized_data['market'])

    # 计算总数
    total_count = sum(len(v) for v in categorized_data.values())

    html_content = f"""
    <html>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background:#f4f7f9; padding:20px;">
        <div style="max-width: 700px; margin: 0 auto; background:#f4f7f9;">
            <div style="background:#1a365d; padding:40px 20px; text-align:center; color:#ffffff; border-radius: 8px 8px 0 0;">
                <h1 style="margin:0; font-size:26px; letter-spacing: 1px;">全球教育 & AI 动态情报</h1>
                <p style="opacity:0.8; font-size:15px; margin-top:10px;">Agent速递：全球7天热点深度追踪</p>
                <p style="font-size:12px; margin-top:15px; background: rgba(255,255,255,0.1); display: inline-block; padding: 5px 15px; border-radius: 20px;">
                    今日情报总量：{total_count} 条精华
                </p>
            </div>
            <table style="width:100%; border-collapse:collapse; margin-top: 10px;">
                {policy_html}
                {ai_html}
                {market_html}
            </table>
            <div style="padding:30px; text-align:center; font-size:12px; color:#a0aec0; line-height: 1.6;">
                本报旨在为上海国际高中教学与升学提供全球视野支持<br>
                国家范围：美、英、加、澳、新、中、日、德、法<br>
                生成日期：{datetime.now().strftime('%Y年%m月%d日')}
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['Subject'] = "Agent速递：全球7天AI与教育洞察"
    msg['From'] = f"Alex Edu Intelligence <{sender}>"
    msg['To'] = ", ".join(receivers)
    msg.attach(MIMEText(html_content, 'html'))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print(f"✅ 深度情报发送成功，共 {total_count} 条内容。")
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

if __name__ == "__main__":
    send_edu_email()
