import os
from fastapi import FastAPI, HTTPException, Depends, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from passlib.context import CryptContext

# 1. VERİTABANI VE GÜVENLİK AYARLARI
DATABASE_URL = "sqlite:///./fiyat_radar_SaaS.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_subscribed = Column(Integer, default=0) # 0=Pasif, 1=Aktif
    products = relationship("Product", back_populates="owner")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    buy_price = Column(Float)
    shipping_cost = Column(Float)
    commission_rate = Column(Float)
    vat_rate = Column(Float)
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="products")

Base.metadata.create_all(bind=engine)

# 2. PROFESYONEL FRONTEND ARAYÜZÜ (KAYIT + GİRİŞ + PANEL + ÖDEME)
HTML_LOGIN_REGISTER = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><title>Fiyat Radarı - Giriş Yap</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 flex items-center justify-center h-screen font-sans">
    <div class="bg-white p-8 rounded-2xl shadow-2xl w-full max-w-md">
        <h2 class="text-2xl font-bold text-center text-indigo-700 mb-6">📡 AKILLI FİYAT RADARI</h2>
        <form action="/login" method="post" class="space-y-4">
            <div>
                <label class="block text-xs font-bold text-gray-500 uppercase">E-Posta</label>
                <input type="email" name="username" required class="w-full mt-1 p-3 border rounded-xl focus:outline-none focus:border-indigo-600">
            </div>
            <div>
                <label class="block text-xs font-bold text-gray-500 uppercase">Şifre</label>
                <input type="password" name="password" required class="w-full mt-1 p-3 border rounded-xl focus:outline-none focus:border-indigo-600">
            </div>
            <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 rounded-xl transition">Giriş Yap</button>
        </form>
        <hr class="my-6">
        <form action="/register" method="post" class="space-y-4">
            <p class="text-center text-xs text-gray-400">Hesabınız yok mu? Hemen ücretsiz kayıt olun:</p>
            <button type="submit" formaction="/register" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2 rounded-xl transition text-sm">Yeni Hesap Oluştur</button>
        </form>
    </div>
</body>
</html>
"""

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><title>Fiyat Radarı - Panel</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body class="bg-gray-50 font-sans antialiased">
    <nav class="bg-indigo-700 text-white shadow-lg px-6 py-4 flex justify-between items-center">
        <div class="flex items-center space-x-3">
            <i class="fa-solid fa-radar fa-2xl text-indigo-200"></i>
            <span class="text-xl font-bold tracking-wider">AKILLI FİYAT RADARI</span>
        </div>
        <div class="flex items-center space-x-4">
            <span id="sub-status" class="px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider text-white">YÜKLENİYOR...</span>
            <a href="/logout" class="text-sm bg-indigo-800 hover:bg-indigo-900 px-3 py-2 rounded-xl">Çıkış Yap</a>
        </div>
    </nav>

    <div class="max-w-7xl mx-auto px-4 py-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div class="space-y-6">
            <div id="payment-box" class="bg-gradient-to-br from-purple-600 to-indigo-800 text-white rounded-2xl shadow-xl p-6 hidden">
                <h3 class="text-lg font-bold mb-2"><i class="fa-solid fa-credit-card mr-2"></i> PRO Sürümüne Abone Ol</h3>
                <p class="text-sm text-indigo-100 mb-6">Aylık sadece 299 TL'ye sınırsız ürün analizi yapın.</p>
                <button onclick="startStripeCheckout()" class="w-full bg-white text-indigo-700 font-bold py-3 rounded-xl hover:bg-indigo-50 transition shadow-md">
                    Stripe ile Güvenli Abone Ol
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
                <h2 class="text-lg font-bold text-gray-900 mb-4">Sadece Sizin Radardaki Ürünleriniz</h2>
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
        let currentUserEmail = "";

        async function checkSubscription() {
            const res = await fetch(API_BASE + '/api/v1/user-status');
            if(res.status === 401) { window.location.href = "/"; return; }
            const user = await res.json();
            currentUserEmail = user.email;
            
            if (user.is_subscribed === 1) {
                document.getElementById('sub-status').className = "bg-emerald-500 px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider text-white";
                document.getElementById('sub-status').innerText = "PRO AKTİF: " + user.email;
                document.getElementById('payment-box').style.display = 'none';
                document.getElementById('form-container').classList.remove('opacity-50');
                document.querySelectorAll('#product-form input, #product-form button').forEach(el => el.removeAttribute('disabled'));
                document.getElementById('submit-btn').className = "w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-xl transition";
                document.getElementById('submit-btn').innerText = "Hesapla ve Ekle";
                fetchDashboard();
            } else {
                document.getElementById('sub-status').className = "bg-red-500 px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider text-white";
                document.getElementById('sub-status').innerText = "ABONELİK PASİF";
                document.getElementById('payment-box').classList.remove('hidden');
            }
        }

        function startStripeCheckout() {
            // Gerçek dünyada Stripe API tetiklenir, burada test amaçlı Stripe simülasyon ödeme ekranına paslıyoruz
            window.location.href = API_BASE + '/api/v1/stripe-success?email=' + currentUserEmail;
        }

        async function fetchDashboard() {
            const res = await fetch(API_BASE + '/api/v1/dashboard-data');
            const data = await res.json();
            const tbody = document.getElementById('product-table-body');
            tbody.innerHTML = '';
            data.products.forEach(p => {
                tbody.insertAdjacentHTML('beforeend', `<tr><td class="py-4 font-medium">\${p.name}</td><td class="py-4">\${p.total_cost} TL</td><td class="py-4 text-amber-600">\${p.break_even} TL</td><td class="py-4 text-indigo-600 font-bold">\${p.rec_price} TL</td></tr>`);
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
            await fetch(API_BASE + '/api/v1/products-ui', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            document.getElementById('product-form').reset();
            fetchDashboard();
        });

        window.onload = checkSubscription;
    </script>
</body>
</html>
"""

# 3. GİRİŞ/KAYIT VE ÖDEME API MOTORU
app = FastAPI()
ACTIVE_SESSION = {} # Basit çerez mekanizması

class ProductCreateSchema(BaseModel):
    name: str; buy_price: float; shipping_cost: float; commission_rate: float; vat_rate: float

@app.get("/", response_class=HTMLResponse)
def login_page():
    return HTML_LOGIN_REGISTER

@app.post("/register")
def register(username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(User).filter(User.email == username).first()
    if user:
        db.close()
        return HTMLResponse("<script>alert('Bu e-posta zaten kayıtlı!'); window.location.href='/';</script>")
    hashed = pwd_context.hash(password)
    new_user = User(email=username, hashed_password=hashed, is_subscribed=0)
    db.add(new_user); db.commit(); db.close()
    return HTMLResponse("<script>alert('Kayıt Başarılı! Şimdi Giriş Yapın.'); window.location.href='/';</script>")

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(User).filter(User.email == username).first()
    if not user or not pwd_context.verify(password, user.hashed_password):
        db.close()
        return HTMLResponse("<script>alert('Hatalı Giriş!'); window.location.href='/';</script>")
    ACTIVE_SESSION["current_user"] = user.email
    db.close()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    if "current_user" not in ACTIVE_SESSION:
        return RedirectResponse(url="/")
    return HTML_DASHBOARD

@app.get("/logout")
def logout():
    ACTIVE_SESSION.pop("current_user", None)
    return RedirectResponse(url="/")

@app.get("/api/v1/user-status")
def user_status():
    if "current_user" not in ACTIVE_SESSION:
        raise HTTPException(status_code=401)
    db = SessionLocal()
    user = db.query(User).filter(User.email == ACTIVE_SESSION["current_user"]).first()
    db.close()
    return {"email": user.email, "is_subscribed": user.is_subscribed}

@app.get("/api/v1/stripe-success")
def stripe_success(email: str):
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.is_subscribed = 1
        db.commit()
    db.close()
    return HTMLResponse("""
        <div style='text-align:center; margin-top:100px; font-family:sans-serif;'>
            <h1 style='color:#10B981;'>💳 Stripe Ödemesi Alındı!</h1>
            <p>299 TL değerindeki SaaS aboneliğiniz hesabınıza tanımlandı.</p>
            <a href='/dashboard' style='background:#4F46E5; color:white; padding:10px 20px; text-decoration:none; border-radius:8px; font-weight:bold;'>Paneli Aç</a>
        </div>
    """)

@app.get("/api/v1/dashboard-data")
def dashboard_data():
    if "current_user" not in ACTIVE_SESSION: raise HTTPException(status_code=401)
    db = SessionLocal()
    user = db.query(User).filter(User.email == ACTIVE_SESSION["current_user"]).first()
    products_db = db.query(Product).filter(Product.user_id == user.id).all()
    
    products_list = []
    for p in products_db:
        costs = p.buy_price + p.shipping_cost
        f = p.commission_rate / 100
        be = costs / (1 - f)
        rec = (costs * 1.25) / (1 - f)
        products_list.append({"name": p.name, "total_cost": round(costs, 2), "break_even": round(be, 2), "rec_price": round(rec, 2)})
    db.close()
    return {"products": products_list}

@app.post("/api/v1/products-ui")
def add_product(data: ProductCreateSchema):
    if "current_user" not in ACTIVE_SESSION: raise HTTPException(status_code=401)
    db = SessionLocal()
    user = db.query(User).filter(User.email == ACTIVE_SESSION["current_user"]).first()
    p = Product(name=data.name, buy_price=data.buy_price, shipping_cost=data.shipping_cost, commission_rate=data.commission_rate, vat_rate=data.vat_rate, user_id=user.id)
    db.add(p); db.commit(); db.close()
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
