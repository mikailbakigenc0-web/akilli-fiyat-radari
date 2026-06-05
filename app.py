# =====================================================================
# SIFIR KURULUM - ÖDEME ENTEGRELİ FİYAT RADARI (COLAB NİHAİ)
# =====================================================================
import datetime
import multiprocessing
import uvicorn
import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker
from pycloudflared import try_cloudflare

# 1. VERİTABANI VE SIFIRLAMA
DATABASE_URL = "sqlite:///./fiyat_radar_odeme_final.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True)
    is_subscribed = Column(Integer, default=0) # 0 = Pasif, 1 = Aktif

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    buy_price = Column(Float)
    shipping_cost = Column(Float)
    commission_rate = Column(Float)
    vat_rate = Column(Float)

class Analysis(Base):
    __tablename__ = "analyses"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer)
    total_cost = Column(Float)
    break_even_price = Column(Float)
    recommended_price = Column(Float)

Base.metadata.create_all(bind=engine)

# 2. ÖDEME KONTROLLÜ MOR-BEYAZ ARAYÜZ
HTML_INTERFACE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Akıllı Fiyat Radarı</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body class="bg-gray-50 font-sans antialiased">
    <nav class="bg-indigo-700 text-white shadow-lg px-6 py-4 flex justify-between items-center">
        <div class="flex items-center space-x-3">
            <i class="fa-solid fa-radar fa-2xl text-indigo-200"></i>
            <span class="text-xl font-bold tracking-wider">AKILLI FİYAT RADARI</span>
        </div>
        <div>
            <span id="sub-status" class="bg-red-500 px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider text-white">ABONELİK PASİF</span>
        </div>
    </nav>

    <div class="max-w-7xl mx-auto px-4 py-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div class="space-y-6">
            <div id="payment-box" class="bg-gradient-to-br from-purple-600 to-indigo-800 text-white rounded-2xl shadow-xl p-6">
                <h3 class="text-lg font-bold mb-2"><i class="fa-solid fa-credit-card mr-2"></i> PRO Sürümüne Abone Ol</h3>
                <p class="text-sm text-indigo-100 mb-6">Aylık sadece 299 TL'ye sınırsız ürün analizi yapın.</p>
                <button onclick="startCheckout()" class="w-full bg-white text-indigo-700 font-bold py-3 rounded-xl hover:bg-indigo-50 transition shadow-md">
                    iyzico ile Güvenli Abone Ol
                </button>
            </div>

            <div class="bg-white rounded-2xl shadow-sm p-6 border border-gray-100 opacity-50" id="form-container">
                <h2 class="text-lg font-bold text-gray-900 mb-4"><i class="fa-solid fa-calculator text-indigo-600 mr-2"></i> Yeni Ürün Girişi</h2>
                <form id="product-form" class="space-y-4">
                    <input type="text" id="p-name" required placeholder="Ürün Adı" class="w-full rounded-xl border p-3 text-sm focus:outline-none" disabled>
                    <div class="grid grid-cols-2 gap-4">
                        <input type="number" id="p-buy" required step="0.01" placeholder="Alış (TL)" class="w-full rounded-xl border p-3 text-sm focus:outline-none" disabled>
                        <input type="number" id="p-shipping" required step="0.01" placeholder="Kargo (TL)" class="w-full rounded-xl border p-3 text-sm focus:outline-none" disabled>
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <input type="number" id="p-commission" required placeholder="Komisyon (%)" class="w-full rounded-xl border p-3 text-sm focus:outline-none" disabled>
                        <input type="number" id="p-vat" required value="20" class="w-full rounded-xl border p-3 text-sm focus:outline-none" disabled>
                    </div>
                    <button type="submit" id="submit-btn" class="w-full bg-gray-400 text-white font-semibold py-3 rounded-xl cursor-not-allowed" disabled>Önce Abone Olmalısınız</button>
                </form>
            </div>
        </div>

        <div class="lg:col-span-2 space-y-6">
            <div class="bg-white rounded-2xl shadow-sm p-6 border border-gray-100">
                <h2 class="text-lg font-bold text-gray-900 mb-4">Radardaki Ürünleriniz</h2>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse text-sm">
                        <thead>
                            <tr class="border-b text-gray-400 uppercase font-bold">
                                <th class="pb-3">Ürün Adı</th>
                                <th class="pb-3">Maliyet</th>
                                <th class="pb-3 text-amber-600">Başa Baş</th>
                                <th class="pb-3 text-indigo-600">Önerilen Satış</th>
                            </tr>
                        </thead>
                        <tbody id="product-table-body" class="text-gray-600 divide-y"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        const API_BASE = window.location.origin;

        async function checkSubscription() {
            const res = await fetch(API_BASE + '/api/v1/user-status');
            const user = await res.json();
            
            if (user.is_subscribed === 1) {
                document.getElementById('sub-status').className = "bg-emerald-500 px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider text-white";
                document.getElementById('sub-status').innerText = "PRO ABONELİK AKTİF";
                document.getElementById('payment-box').style.display = 'none';
                document.getElementById('form-container').classList.remove('opacity-50');
                document.querySelectorAll('#product-form input, #product-form button').forEach(el => el.removeAttribute('disabled'));
                document.getElementById('submit-btn').className = "w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-xl transition";
                document.getElementById('submit-btn').innerText = "Hesapla ve Ekle";
                fetchDashboard();
            }
        }

        async function startCheckout() {
            // iyzico simülasyon sayfasına yönlendiriyoruz
            window.location.href = API_BASE + '/api/v1/pay-success';
        }

        async function fetchDashboard() {
            const res = await fetch(API_BASE + '/api/v1/dashboard-data');
            const data = await res.json();
            const tbody = document.getElementById('product-table-body');
            tbody.innerHTML = '';
            data.products.forEach(p => {
                let row = '<tr>' +
                    '<td class="py-4 font-medium">' + p.name + '</td>' +
                    '<td class="py-4">' + p.total_cost + ' TL</td>' +
                    '<td class="py-4 text-amber-600">' + p.break_even + ' TL</td>' +
                    '<td class="py-4 text-indigo-600 font-bold">' + p.rec_price + ' TL</td>' +
                '</tr>';
                tbody.insertAdjacentHTML('beforeend', row);
            });
        }

        document.getElementById('product-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                name: document.getElementById('p-name').value,
                buy_price: parseFloat(document.getElementById('p-buy').value),
                shipping_cost: parseFloat(document.getElementById('p-shipping').value),
                commission_rate: parseFloat(document.getElementById('p-commission').value),
                vat_rate: parseFloat(document.getElementById('p-vat').value)
            };
            const res = await fetch(API_BASE + '/api/v1/products-ui', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res.ok) { document.getElementById('product-form').reset(); fetchDashboard(); }
        });

        window.onload = checkSubscription;
    </script>
</body>
</html>
"""

# 3. FASTAPI VE SIMÜLE EDİLMİŞ ÖDEME API'LERİ
app = FastAPI()

class ProductCreateSchema(BaseModel):
    name: str; buy_price: float; shipping_cost: float; commission_rate: float; vat_rate: float

@app.get("/", response_class=HTMLResponse)
def home(): return HTML_INTERFACE

@app.get("/api/v1/user-status")
def get_user_status():
    db = SessionLocal()
    user = db.query(User).first()
    if not user:
        user = User(email="demo@radar.com", is_subscribed=0)
        db.add(user); db.commit()
    db.close()
    return {"is_subscribed": user.is_subscribed}

@app.get("/api/v1/pay-success")
def payment_success_callback():
    db = SessionLocal()
    user = db.query(User).first()
    if user: user.is_subscribed = 1; db.commit()
    db.close()
    return HTMLResponse(content="""
        <div style='text-align:center; margin-top:100px; font-family:sans-serif;'>
            <h1 style='color:#10B981;'>🎉 iyzico Ödemesi Başarılı!</h1>
            <p>Aboneliğiniz başarıyla aktif edildi. Şimdi sistemi sınırsız kullanabilirsiniz.</p>
            <br>
            <a href='/' style='background:#4F46E5; color:white; padding:12px 24px; text-decoration:none; border-radius:10px; font-weight:bold;'>Sisteme Giriş Yap</a>
        </div>
    """)

@app.get("/api/v1/dashboard-data")
def get_data():
    db = SessionLocal()
    products_db = db.query(Product).all()
    products_list = []
    for p in products_db:
        an = db.query(Analysis).filter(Analysis.product_id == p.id).order_by(Analysis.id.desc()).first()
        products_list.append({"name": p.name, "total_cost": round(p.buy_price + p.shipping_cost, 2), "break_even": an.break_even_price if an else 0, "rec_price": an.recommended_price if an else 0})
    db.close()
    return {"products": products_list}

@app.post("/api/v1/products-ui")
def create_p(data: ProductCreateSchema):
    db = SessionLocal()
    p = Product(name=data.name, buy_price=data.buy_price, shipping_cost=data.shipping_cost, commission_rate=data.commission_rate, vat_rate=data.vat_rate)
    db.add(p); db.commit(); db.refresh(p)
    costs = p.buy_price + p.shipping_cost; f = p.commission_rate / 100
    be = costs / (1 - f); rec = (costs * 1.25) / (1 - f)
    an = Analysis(product_id=p.id, total_cost=round(costs, 2), break_even_price=round(be, 2), recommended_price=round(rec, 2))
    db.add(an); db.commit(); db.close()
    return {"status": "success"}

# 4. SÜREÇ BAŞLATMA VE TÜNEL
try:
    if api_process.is_alive(): api_process.terminate()
except NameError: pass

def run_api(): uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
api_process = multiprocessing.Process(target=run_api); api_process.start(); time.sleep(2)

cl_tunnel = try_cloudflare(port=8000)
print(f"\n🎉 SİSTEM EKSİKSİZ HAZIR! Ödeme Kontrollü Panel Linki:\n👉 {str(cl_tunnel).strip()} 👈")