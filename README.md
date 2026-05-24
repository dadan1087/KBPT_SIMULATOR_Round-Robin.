# K-BBPT Simulator

Simulator sistem bisnis **K-BBPT** dengan dual income engine:  
- **Auto Cuan** – passive income dari jaringan (binary tree, spillover round-robin, komisi 8 level, bonus sponsor berantai).  
- **Auto Rich** – active income dari transaksi downline (unlimited direct, komisi 10 level tanpa syarat).

Aplikasi dibuat dengan [Streamlit](https://streamlit.io) untuk membantu memahami alur komisi, placement, dan independensi kedua program.

## Fitur Utama

- Registrasi member dengan **spillover round-robin dimulai dari kanan** (binary placement).
- Belanja produk untuk **Auto Cuan** (wajib ≥Rp100.000 untuk status aktif) atau **Auto Rich** (bebas).
- Perhitungan komisi otomatis sesuai dokumen teknis:
  - **Auto Cuan**: persentase berjenjang 8 level (dapat diubah) + bonus sponsor 20% berantai.
  - **Auto Rich**: persentase berjenjang 10 level (dapat diubah).
- Visualisasi pohon **placement tree** (binary) dan **sponsor tree** (unlimited).
- Pengaturan fleksibel (persentase komisi, level, batas belanja aktif, dll) tanpa perlu deploy ulang.
- Ringkasan keuangan perusahaan (cash in, total bonus, nett).

## Cara Instalasi

1. Pastikan Python 3.8+ sudah terpasang.
2. Clone atau download folder proyek ini.
3. Buka terminal di folder proyek, lalu buat virtual environment (opsional namun disarankan):
   ```bash
   python -m venv venv
   source venv/bin/activate      # Linux/macOS
   venv\Scripts\activate         # Windows
