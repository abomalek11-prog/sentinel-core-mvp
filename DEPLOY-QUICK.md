# Deploy Instructions — ملخص سريع

## تطوير محلي (Local)
```bash
# 1. تثبيت المتطلبات
uv sync

# 2. ابدأ الـ Backend (Terminal 1)
$env:PYTHONPATH = "src"
uvicorn api.main:app --reload --port 8000

# 3. ابدأ الـ Frontend (Terminal 2)
npm run dev

# 4. اذهب إلى http://localhost:3000
```

---

## نشر (Production - Render + Vercel)

### الخطوة 1️⃣: نشر الـ Backend على Render

1. **Push إلى GitHub:**
   ```bash
   git add .
   git commit -m "Ready for deployment"
   git push
   ```

2. **على Render Dashboard (https://render.com):**
   - اختر **New** → **Web Service**
   - اختر GitHub repository
   - Render سيكتشف `Dockerfile` و `render.yaml` تلقائياً
   - أضف Environment Variables (SENTINEL_GITHUB_TOKEN, إلخ)
   - اضغط **Create Web Service**
   - انتظر للحصول على URL مثل: `https://sentinel-core-backend.onrender.com`

### الخطوة 2️⃣: تحديث الـ Frontend على Vercel

1. **في Vercel Dashboard:**
   - اذهب إلى **Settings** → **Environment Variables**
   - أضف: `NEXT_PUBLIC_API_URL = https://sentinel-core-backend.onrender.com`
   - اضغط **Save**
   - اضغط **Redeploy**

2. **اختبر:**
   ```bash
   curl https://sentinel-core-backend.onrender.com/health
   # يجب ترى: {"status":"ok",...}
   ```

---

## المزيد

لـ details كاملة، شوف [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
