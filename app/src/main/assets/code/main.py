const express = require('express');
const axios = require('axios');
const admin = require('firebase-admin');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
app.use(express.json());

// ---------------------------------------------------------
// 1. تهيئة الفايربيس (Firestore)
// ---------------------------------------------------------
const serviceAccount = require('./serviceAccountKey.json'); // ملف المفاتيح مالتك
admin.initializeApp({
  credential: admin.credential.cert(serviceAccount)
});
const db = admin.firestore();

// ---------------------------------------------------------
// 2. تشغيل البروكسي الداخلي المدمج بداخل نفس التطبيق
// ---------------------------------------------------------
// يشتغل سيرفر البروكسي على المسار /proxy لتمرير الطلبات وتخطي الحجب
app.use('/proxy', createProxyMiddleware({
  target: 'https://azoramanga.com', // رابط الموقع المستهدف
  changeOrigin: true,
  pathRewrite: { '^/proxy': '' },
  onProxyReq: (proxyReq) => {
    proxyReq.setHeader('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36');
  }
}));

// ---------------------------------------------------------
// 3. دالة الرفع الشاملة للـ Firestore (مع كل الحقول المطلوبة)
// ---------------------------------------------------------
async function uploadMangaToFirestore(mangaData) {
  try {
    const docRef = db.collection('manga').doc(mangaData.id);
    
    // استخدام merge: true يحافظ على الفصول والأرشيف القديم ويحدث البيانات
    await docRef.set({
      title: mangaData.title,
      cover: mangaData.cover,
      sourceUrl: mangaData.url,
      sourceSite: "أوزورا",
      type: mangaData.type || "مانهوا",
      status: mangaData.status || "مستمر",
      latestChapter: mangaData.latestChapter || "الفصل 1",
      createdAt: admin.firestore.FieldValue.serverTimestamp(),
      updatedAt: admin.firestore.FieldValue.serverTimestamp()
    }, { merge: true });

    console.log(`[+] تم الرفع/التحديث الشامل: ${mangaData.title}`);
  } catch (err) {
    console.error(`[-] خطأ في رفع ${mangaData.title}:`, err.message);
  }
}

// ---------------------------------------------------------
// 4. منطق السحب الشامل (يسحب القديم والجديد من صفحة 1 إلى النهاية)
// ---------------------------------------------------------
async function startFullScrape() {
  console.log("🚀 بدأ السحب الشامل والكامل (القديم + الجديد)...");
  
  let page = 1;
  let hasNextPage = true;

  while (hasNextPage) {
    try {
      console.log(`🔎 سحب الصفحة رقم: ${page}`);
      
      // الطلب يمر عبر البروكسي الداخلي المدمج مباشرة (127.0.0.1:3000/proxy)
      const response = await axios.get(`http://127.0.0.1:3000/proxy/manga?page=${page}`);
      
      // استخراج الأعمال من الصفحة
      const mangaList = extractMangaFromHtml(response.data);

      // إذا وصلت الصفحة لآخر أرشيف وماكو بعد أعمال تتوقف الحلقة
      if (!mangaList || mangaList.length === 0) {
        console.log("✅ اكتمل السحب الشامل لجميع الصفحات والأرشيف القديم والجديد بنجاح!");
        hasNextPage = false;
        break;
      }

      // رفع كل العمل المجلوب فوراً وبدون استثناء أي عنصر
      for (const manga of mangaList) {
        await uploadMangaToFirestore(manga);
      }

      page++; // الانتقال للصفحة التالية حتى يمسح كامل الموقع
      
      // تأخير بسيط ثانية واحدة بين الصفحة والأخرى حتى ما ينحظر البروكسي
      await new Promise(res => setTimeout(res, 1000));

    } catch (error) {
      console.error(`❌ خطأ في الصفحة ${page}، إعادة المحاولة...`, error.message);
      await new Promise(res => setTimeout(res, 3000));
    }
  }
}

// دالة تفكيك البيانات (تستبدلها بمنطق الساحب الخاص بك)
function extractMangaFromHtml(html) {
  // هنا كود استخراج المانغا (Cheerio أو regex)
  return []; 
}

// ---------------------------------------------------------
// 5. تشغيل السيرفر الموحد وبدء السحب التلقائي
// ---------------------------------------------------------
const PORT = 3000;
app.listen(PORT, () => {
  console.log(`⚡ البروكسي والساحب شغالين سوية بملف واحد على المنفذ ${PORT}`);
  
  // يبدأ السحب الشامل فور تشغيل التطبيق
  startFullScrape();
});
