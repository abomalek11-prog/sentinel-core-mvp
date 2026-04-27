# نشر Sentinel Core Backend على Render

## الخطوات السريعة

### 1️⃣ حضّر مستودع GitHub

```bash
# تأكد أن الـ code محفوظ في GitHub
git add .
git commit -m "Add Dockerfile and render.yaml for deployment"
git push origin main
```

### 2️⃣ إنشاء حساب Render (إذا لم تكن قد فعلت)

- اذهب إلى https://render.com
- سجل باستخدام GitHub
- اختر "Connect GitHub repository"

### 3️⃣ نشر الـ Backend

#### الطريقة الأولى: استخدام `render.yaml` (موصى به)

1. في Render Dashboard، اختر **"New +"** → **"Web Service"**
2. اختر **"Deploy from GitHub"**
3. ابحث عن `sentinel-core-mvp`
4. اختر **"I own this repository"**
5. Render سيكتشف تلقائياً `render.yaml` ويستخدمه
6. اضغط **"Create Web Service"**

#### الطريقة الثانية: الإعداد اليدوي

1. **New Web Service**
2. اختر GitHub repository: `sentinel-core-mvp`
3. اسم الـ Service: `sentinel-core-backend`
4. البيئة: **Docker**
5. **Build Command**: `docker build -t sentinel-api .`
6. **Start Command**: (اترك فارغاً، سيستخدم Dockerfile)
7. خطة: **Free**

### 4️⃣ إضافة المتغيرات البيئية (Environment Variables)

في Render Dashboard، اذهب إلى **Environment**:

```
SENTINEL_GITHUB_TOKEN=<your_github_pat>
SENTINEL_LOG_LEVEL=INFO
SENTINEL_JSON_LOGS=true
```

احصل على `SENTINEL_GITHUB_TOKEN`:
- اذهب إلى https://github.com/settings/tokens
- اختر **"Generate new token"** → **"Generate new token (classic)"**
- لا تحتاج scopes خاصة
- انسخ الـ token إلى Render

### 5️⃣ الانتظار للـ Deploy

- Render سيبني الـ Docker image
- قد يستغرق 3-5 دقائق
- بمجرد النجاح، ستحصل على URL مثل:
  ```
  https://sentinel-core-backend.onrender.com
  ```

### 6️⃣ تحديث الـ Frontend

الآن حدث الـ Frontend للاتصال بـ Backend المنشور:

**في Vercel Dashboard:**

1. اذهب إلى **Settings** → **Environment Variables**
2. أضف متغير جديد:
   ```
   NEXT_PUBLIC_API_URL = https://sentinel-core-backend.onrender.com
   ```
3. اضغط **Save** و **Redeploy**

### 7️⃣ اختبار الاتصال

```bash
# اختبر الـ Backend مباشرة
curl https://sentinel-core-backend.onrender.com/health

# نتيجة متوقعة:
# {"status":"ok","version":"0.1.0","llm_ready":true,"llm_model":"openai/gpt-4o-mini"}

# اختبر الـ Frontend
# افتح https://sentinel-core-frontend-ruddy.vercel.app
# ثم جرّب "Analyze"
```

---

## ملاحظات مهمة

### تكاليف
- **Render Free Tier**: مجاني تماماً، لكن الخادم قد ينام بعد 15 دقيقة من عدم الاستخدام
- إذا أردت uptime 24/7، ارقِ إلى **Starter** ($5/شهر)

### الأداء
- الـ Free tier قد يكون بطيء على الطلبات الأولى (cold start)
- استخدم `uv` بدلاً من `pip` لتسريع التثبيت

### الأمان
- **NEVER** ضع API keys مباشرة في `render.yaml`
- استخدم **Environment Variables** في Dashboard
- استخدم `.env.local` للتطوير المحلي فقط

---

## استكشاف الأخطاء

### الخادم لا يشتغل

```bash
# شوف الـ Logs في Render Dashboard
# عادة المشكلة في missing environment variables

# تحقق من الـ Health Check
curl https://sentinel-core-backend.onrender.com/health
```

### الـ Frontend لا يتصل

```bash
# تحقق من NEXT_PUBLIC_API_URL
# جرّب في browser console:
fetch('https://sentinel-core-backend.onrender.com/health').then(r => r.json()).then(console.log)
```

### أخطاء CORS

- إذا واجهت CORS errors، تحقق من `api/main.py`
- الـ CORS middleware يسمح بـ all origins (`allow_origins=["*"]`)

---

## الخطوات التالية (Advanced)

### استخدام Database
إذا أردت حفظ التحليلات في قاعدة بيانات:

```yaml
# في render.yaml
services:
  - type: pserv
    name: sentinel-db
    ipAllowList: []
    databaseName: sentinel
    user: sentinel_user
    plan: free
    postgresMajorVersion: 15
```

### Custom Domain
- في Render Dashboard → Settings → Custom Domain
- أضف النطاق الخاص بك

---

## الدعم

إذا واجهت مشاكل:
- تحقق من Render Logs
- تحقق من الـ Environment Variables
- جرّب deployment محلي أولاً: `docker build -t sentinel . && docker run -p 8000:8000 sentinel`
