# =====================================================================
# README.md DOSYASINI OTOMATİK OLUŞTURMA VE İNDİRME HÜCRESİ
# =====================================================================
import os
from google.colab import files

readme_icerik = """# 📡 Akıllı Fiyat Radarı (SaaS Prototip)

Bu proje, e-ticaret satıcılarının ürün maliyetlerini, kargo ücretlerini, platform komisyonlarını ve KDV oranlarını hesaplayarak **başa baş noktasını** ve **önerilen satış fiyatını** anlık olarak çıkaran bir akıllı analiz aracıdır.

## 🚀 Özellikler
* **Abonelik Kilidi (iyzico Entegrasyonu):** Kullanıcılar sisteme abone olana kadar arayüz kilitli kalır. Güvenli ödeme yapıldıktan sonra tüm sistem aktif olur.
* **Anlık Hesaplama Motoru:** Komisyon ve maliyetleri hatasız hesaplar.
* **Lokal Veritabanı:** Ürün verilerini ve analiz geçmişini güvenle saklar.
* **Modern Arayüz:** Tailwind CSS ile güçlendirilmiş şık mor-beyaz tasarım.

## 🛠️ Teknolojiler
* **Backend:** Python, FastAPI, Uvicorn
* **Veritabanı & ORM:** SQLite, SQLAlchemy
* **Frontend:** HTML5, JavaScript, Tailwind CSS, FontAwesome

