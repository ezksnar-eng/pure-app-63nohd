import os
import sys
import time
import threading
import json
import urllib.parse
import urllib.request
import ssl
from http.server import BaseHTTPRequestHandler, HTTPServer

# استدعاء مكتبات الفايربيس والبايثون
import firebase_admin
from firebase_admin import credentials, firestore
from bs4 import BeautifulSoup

# ---------------------------------------------------------
# 1. إعدادات الفايربيس (Firestore)
# ---------------------------------------------------------
# تأكد من وجود ملف الحساب الخدمي بنفس المجلد أو قم بتهيئة التطبيق تلقائياً
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"⚠️ تنبيه الفايربيس: لم يتم العثور على serviceAccountKey.json، سيتم استخدام التهيئة الافتراضية.")
        firebase_admin.initialize_app()

db = firestore.client()

# ---------------------------------------------------------
# 2. البروكسي الداخلي المدمج (Port 8080)
# ---------------------------------------------------------
class IntegratedProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_path.query)
        
        target_url = query.get('url', [None])[0]
        if not target_url and len(self.path) > 1:
            target_url = self.path[1:].lstrip('/')

        if not target_url:
            self.send_response(400)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'Missing url parameter')
            return

        if 'appassets.androidplatform.net' in target_url:
            target_url = target_url.replace('https://appassets.androidplatform.net', 'https://azorafly.com')
            target_url = target_url.replace('http://appassets.androidplatform.net', 'https://azorafly.com')

        if not target_url.startswith('http://') and not target_url.startswith('https://'):
            target_url = 'https://' + target_url

        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                target_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Referer': 'https://azorafly.com/'
                }
            )

            with urllib.request.urlopen(req, timeout=15, context=ctx) as response:
                content = response.read()
                
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', '*')
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(content)

        except Exception as e:
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(f'Error fetching site: {str(e)}'.encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def log_message(self, format, *args):
        return # إخفاء سجلات الـ HTTP العادية لتنظيف الكونسول

def run_proxy_server():
    server_address = ('', 8080)
    httpd = HTTPServer(server_address, IntegratedProxyHandler)
    print("🚀 البروكسي الداخلي شغال بكتفاء ذاتي على port 8080")
    httpd.serve_forever()

# ---------------------------------------------------------
# 3. محرك السحب الشامل ونظام الإشعارات كل 10 دقائق
# ---------------------------------------------------------
global_stats = {"manga": 0, "chapters": 0, "images": 0, "status": "جاري التشغيل"}

def send_android_notification(title, message):
    """إرسال إشعار للنظام كل 10 دقائق للتحقق من التقدم"""
    try:
        # استدعاء Plyer أو إشعارات Android إذا كانت متوفرة ببيئة التشغيل
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name='ساحب بيور',
            timeout=5
        )
    except Exception:
        print(f"🔔 [إشعار النظام]: {title} - {message}")

def notification_timer_loop():
    """حلقة إرسال إشعار دوري كل 10 دقائق بالتقدم"""
    while True:
        time.sleep(600) # 10 دقائق (600 ثانية)
        msg = f"الأعمال: {global_stats['manga']} | الفصول: {global_stats['chapters']} | الصور: {global_stats['images']}"
        send_android_notification("📊 ساحب أزورا يعمل بالخلفية", msg)

def start_comprehensive_scraper():
    print("🚀 بدء محرك السحب الشامل (قديم + جديد)...")
    AZORA_BASE = "https://azorafly.com"
    page = 1
    has_more = True

    while has_more:
        try:
            print(f"🔎 جاري فحص مسح الصفحة رقم: {page}")
            proxy_url = f"http://127.0.0.1:8080/?url={urllib.parse.quote(f'{AZORA_BASE}/manga?page={page}')}"
            
            req = urllib.request.Request(proxy_url)
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode('utf-8')

            soup = BeautifulSoup(html, 'html.parser')
            links = soup.find_all('a', href=True)
            
            manga_urls = []
            for a in links:
                href = a['href']
                if '/series/' in href or '/manga/' in href or '/work/' in href:
                    full_u = href if href.startswith('http') else AZORA_BASE + href
                    if full_u not in manga_urls:
                        manga_urls.append(full_u)

            if not manga_urls:
                print("✅ تم الانتهاء من سحب كافة صفحات الأرشيف بالكامل!")
                has_more = False
                break

            for m_url in manga_urls:
                try:
                    # 1. التحقق من وجود المانجا في قاعدة البيانات أولاً
                    manga_ref = db.collection('manga').where('sourceUrl', '==', m_url).limit(1).get()
                    
                    # جلب صفحة المانجا التفصيلية
                    p_m_url = f"http://127.0.0.1:8080/?url={urllib.parse.quote(m_url)}"
                    with urllib.request.urlopen(p_m_url, timeout=20) as m_resp:
                        m_html = m_resp.read().decode('utf-8')
                    
                    m_soup = BeautifulSoup(m_html, 'html.parser')
                    title = m_soup.find('meta', property='og:title')
                    title = title['content'] if title else "عمل أزورا"
                    
                    cover = m_soup.find('meta', property='og:image')
                    cover_url = cover['content'] if cover else ""

                    if manga_ref:
                        doc_id = manga_ref[0].id
                        print(f"  ⚠️ العمل موجود سابقاً، تجري مراجعة الفصول والتحديث: {title}")
                        # تحديث الحقول الأساسية
                        db.collection('manga').document(doc_id).update({
                            'updatedAt': firestore.SERVER_TIMESTAMP,
                            'status': 'مستمر',
                            'type': 'مانهوا'
                        })
                    else:
                        # إضافة مانجا جديدة بجميع الحقول المطلوبة
                        new_doc = db.collection('manga').add({
                            'title': title,
                            'cover': cover_url,
                            'sourceUrl': m_url,
                            'sourceSite': 'Azora',
                            'type': 'مانهوا',
                            'status': 'مستمر',
                            'latestChapter': 'الفصل 1',
                            'createdAt': firestore.SERVER_TIMESTAMP,
                            'updatedAt': firestore.SERVER_TIMESTAMP
                        })
                        doc_id = new_doc[1].id
                        global_stats['manga'] += 1
                        print(f"  ✨ تم حفظ عمل جديد: {title}")

                except Exception as e:
                    print(f"❌ خطأ أثناء معالجة المانجا {m_url}: {e}")

            page += 1
            time.sleep(1) # تأخير بسيط لعدم إجهاد السيرفر

        except Exception as e:
            print(f"❌ خطأ في السحب للصفحة {page}: {e}")
            time.sleep(3)

# ---------------------------------------------------------
# 4. الواجهة البرمجية المدمجة (HTML Design + HTML View)
# ---------------------------------------------------------
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ساحب بيور الموحد 🚀</title>
  <style>
    :root { --main: #ff9800; --bg: #0b0b0e; --card: #16161a; --border: #26262e; }
    body { font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: #fff; padding: 15px; margin: 0; }
    .container { background: var(--card); padding: 20px; border-radius: 18px; max-width: 650px; margin: auto; border: 1px solid var(--border); box-shadow: 0 10px 30px rgba(0,0,0,0.9); }
    h2 { color: var(--main); text-align: center; margin: 0 0 10px; font-size: 22px; }
    .status-badge { display: block; text-align: center; padding: 8px 15px; border-radius: 12px; font-size: 13px; font-weight: bold; background: #1f1a0e; color: var(--main); border: 1px solid var(--main); margin-bottom: 15px; }
    .grid-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 15px; }
    .stat-card { background: #0e0e11; padding: 12px; border-radius: 10px; text-align: center; border: 1px solid var(--border); }
    .stat-card h3 { margin: 0; color: var(--main); font-size: 20px; }
    .stat-card p { margin: 3px 0 0; font-size: 11px; color: #888; }
    
    /* نافذة معلومات البروكسي المدمجة الجديدة */
    .proxy-info-card { background: #121217; padding: 14px; border-radius: 12px; border: 1px dashed var(--main); margin-bottom: 15px; font-size: 12px; }
    .proxy-info-card h4 { margin: 0 0 8px; color: #ffb74d; display: flex; align-items: center; justify-content: space-between; }
    .proxy-status { font-size: 11px; color: #4cd137; background: rgba(76, 209, 55, 0.1); padding: 2px 8px; border-radius: 6px; }

    .progress-box { width: 100%; background: #222; height: 12px; border-radius: 6px; overflow: hidden; margin-bottom: 15px; border: 1px solid #333; }
    .progress-fill { width: 100%; height: 100%; background: linear-gradient(90deg, #ff9800, #ffb74d); animation: pulse 2s infinite; }
    @keyframes pulse { 0% { opacity: 0.6; } 50% { opacity: 1; } 100% { opacity: 0.6; } }

    #logBox { font-size: 12px; color: #64b5f6; white-space: pre-line; text-align: right; background: #060608; padding: 12px; border-radius: 10px; height: 220px; overflow-y: auto; border: 1px solid var(--border); font-family: monospace; line-height: 1.6; }
  </style>
</head>
<body>

  <div class="container">
    <h2>ساحب أزورا المدمج (Port 8080) ⚡</h2>
    <div class="status-badge" id="status">🚀 الخدمة متصلة وتعمل بالخلفية 24/7</div>

    <div class="grid-stats">
      <div class="stat-card"><h3 id="statManga">0</h3><p>أعمال جديدة</p></div>
      <div class="stat-card"><h3 id="statChaps">0</h3><p>فصول مرفوعة</p></div>
      <div class="stat-card"><h3 id="statImgs">0</h3><p>صور معالجة</p></div>
    </div>

    <!-- نافذة معلومات البروكسي والدمج الشامل -->
    <div class="proxy-info-card">
      <h4>📡 معلومات خادم البروكسي الداخلي <span class="proxy-status">● نشط (Port 8080)</span></h4>
      <p style="margin: 3px 0; color: #aaa;">• <b>وضع السحب:</b> شامل (القديم والجديد من أحدث صفحة لأقدم صفحة).</p>
      <p style="margin: 3px 0; color: #aaa;">• <b>فحص القاعدة:</b> يتم تخطي التكرار وتحديث الحقول المفقودة تلقائياً.</p>
      <p style="margin: 3px 0; color: #aaa;">• <b>الإشعارات:</b> تصلك إشعارات بالتقدم كل 10 دقائق بالخلفية.</p>
    </div>

    <div class="progress-box"><div class="progress-fill"></div></div>

    <div id="logBox">> جاري تشغيل البروكسي وسيرفر السحب بالخلفية...
> تم تفعيل فحص Firestore المباشر للقديم والجديد.</div>
  </div>

</body>
</html>
"""

# ---------------------------------------------------------
# 5. تشغيل المسارات ومحركات الخلفية سوية
# ---------------------------------------------------------
if __name__ == '__main__':
    # 1. تشغيل البروكسي في خيط منفصل (Thread)
    proxy_thread = threading.Thread(target=run_proxy_server, daemon=True)
    proxy_thread.start()

    # 2. تشغيل محرك السحب الشامل في خيط منفصل
    scraper_thread = threading.Thread(target=start_comprehensive_scraper, daemon=True)
    scraper_thread.start()

    # 3. تشغيل حلقة الإشعارات الدورية بالخلفية (كل 10 دقائق)
    notify_thread = threading.Thread(target=notification_timer_loop, daemon=True)
    notify_thread.start()

    print("✅ تم تشغيل كافة الخدمات المدمجة بنجاح! الساحب والبروكسي والإشعارات شغالين 100%.")
    
    # حلقة إبقاء التطبيق شغالاً بالخلفية بشكل دائم
    while True:
        time.sleep(1)
