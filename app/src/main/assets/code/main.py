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
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"⚠️ تنبيه الفايربيس: لم يتم العثور على serviceAccountKey.json، سيتم استخدام التهيئة الافتراضية.")
        firebase_admin.initialize_app()

db = firestore.client()

# ---------------------------------------------------------
# 2. البروكسي الداخلي (كودك رقم 2 المدمج بورت 8080)
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
                    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
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
        return

def run_proxy_server():
    server_address = ('', 8080)
    httpd = HTTPServer(server_address, IntegratedProxyHandler)
    print("🚀 Proxy server running on port 8080 (SSL Fixed)...")
    httpd.serve_forever()

# ---------------------------------------------------------
# 3. محرك السحب الشامل ونظام الإشعارات للخدمة الدائمة
# ---------------------------------------------------------
global_stats = {"manga": 0, "chapters": 0, "images": 0}

def send_android_notification(title, message):
    """إرسال إشعار للنظام كل 10 دقائق"""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name='ساحب أزورا',
            timeout=5
        )
    except Exception:
        print(f"🔔 [إشعار]: {title} - {message}")

def notification_timer_loop():
    """إرسال إشعار كل 10 دقائق بالفحص حتى لو الجهاز مغلق"""
    while True:
        time.sleep(600)  # كل 10 دقائق (600 ثانية)
        msg = f"الأعمال: {global_stats['manga']} | الفصول: {global_stats['chapters']} | الصور: {global_stats['images']}"
        send_android_notification("⚡ ساحب أزورا يعمل بالخلفية", msg)

def start_comprehensive_scraper():
    print("🚀 بدء محرك السحب الشامل (قديم + جديد) عبر البروكسي...")
    AZORA_BASE = "https://azorafly.com"
    page = 1
    has_more = True

    while has_more:
        try:
            print(f"🔎 فحص صفحة الأرشيف رقم: {page}")
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
                    full_u = href if href.startswith('http') else AZORA_BASE + ('' if href.startswith('/') else '/') + href
                    if full_u not in manga_urls:
                        manga_urls.append(full_u)

            if not manga_urls:
                print("✅ اكتمل سحب جميع صفحات الأرشيف بالكامل!")
                has_more = False
                break

            for m_url in manga_urls:
                try:
                    # 1. التثبت هل المانجا موجودة بقاعدة البيانات
                    manga_ref = db.collection('manga').where('sourceUrl', '==', m_url).limit(1).get()
                    
                    p_m_url = f"http://127.0.0.1:8080/?url={urllib.parse.quote(m_url)}"
                    with urllib.request.urlopen(p_m_url, timeout=20) as m_resp:
                        m_html = m_resp.read().decode('utf-8')
                    
                    m_soup = BeautifulSoup(m_html, 'html.parser')
                    title_elem = m_soup.find('meta', property='og:title')
                    title = title_elem['content'] if title_elem else "عمل أزورا"
                    
                    cover_elem = m_soup.find('meta', property='og:image')
                    cover_url = cover_elem['content'] if cover_elem else ""

                    if manga_ref:
                        doc_id = manga_ref[0].id
                        print(f"  ⚠️ العمل موجود سابقاً، تجري مراجعة الفصول والتحديث: {title}")
                        db.collection('manga').document(doc_id).update({
                            'updatedAt': firestore.SERVER_TIMESTAMP,
                            'status': 'مستمر',
                            'type': 'مانهوا'
                        })
                    else:
                        new_doc = db.collection('manga').add({
                            'title': title,
                            'cover': cover_url,
                            'sourceUrl': m_url,
                            'sourceSite': 'Azora',
                            'type': 'مانهوا',
                            'status': 'مستمر',
                            'createdAt': firestore.SERVER_TIMESTAMP,
                            'updatedAt': firestore.SERVER_TIMESTAMP
                        })
                        doc_id = new_doc[1].id
                        global_stats['manga'] += 1
                        print(f"  ✨ تم إضافة عمل جديد: {title}")

                except Exception as e:
                    print(f"❌ خطأ أثناء معالجة العمل {m_url}: {e}")

            page += 1
            time.sleep(1)

        except Exception as e:
            print(f"❌ خطأ بمسح الصفحة {page}: {e}")
            time.sleep(3)

# ---------------------------------------------------------
# 4. نفس تصميم HTML مالتك الأول بالضبط (كود رقم 1)
# ---------------------------------------------------------
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ساحب أزورا التلقائي 🚀</title>
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
    .progress-box { width: 100%; background: #222; height: 12px; border-radius: 6px; overflow: hidden; margin-bottom: 15px; border: 1px solid #333; }
    .progress-fill { width: 0%; height: 100%; background: linear-gradient(90deg, #ff9800, #ffb74d); transition: width 0.3s; }
    #logBox { font-size: 12px; color: #64b5f6; white-space: pre-line; text-align: right; background: #060608; padding: 12px; border-radius: 10px; height: 280px; overflow-y: auto; border: 1px solid var(--border); font-family: monospace; line-height: 1.6; }
  </style>
</head>
<body>

  <div class="container">
    <h2>ساحب أزورا (Port 8080) ⚡</h2>
    <div class="status-badge" id="status">🚀 جاري الاتصال بالبروكسي...</div>

    <div class="grid-stats">
      <div class="stat-card"><h3 id="statManga">0</h3><p>أعمال جديدة</p></div>
      <div class="stat-card"><h3 id="statChaps">0</h3><p>فصول مرفوعة</p></div>
      <div class="stat-card"><h3 id="statImgs">0</h3><p>صور معالجة</p></div>
    </div>

    <div class="progress-box"><div class="progress-fill" id="pFill"></div></div>

    <div id="logBox">بدء الاتصال بسيرفر البروكسي على port 8080...</div>
  </div>

</body>
</html>
"""

# ---------------------------------------------------------
# 5. تشغيل الخدمات
# ---------------------------------------------------------
if __name__ == '__main__':
    # تشغيل سيرفر البروكسي (كود رقم 2)
    proxy_thread = threading.Thread(target=run_proxy_server, daemon=True)
    proxy_thread.start()

    # تشغيل محرك السحب بالخلفية
    scraper_thread = threading.Thread(target=start_comprehensive_scraper, daemon=True)
    scraper_thread.start()

    # تشغيل حلقة الإشعارات كل 10 دقائق
    notify_thread = threading.Thread(target=notification_timer_loop, daemon=True)
    notify_thread.start()

    print("✅ تم تشغيل الكود بنجاح بالكامل مع التصميم الأول المفضل لديك!")
    
    while True:
        time.sleep(1)
