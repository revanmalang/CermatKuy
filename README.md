# CermatKuy

Sistem bantu deteksi dan verifikasi awal berita/informasi yang diduga hoaks, berbasis analisis heuristik lokal (pola bahasa, gaya penulisan, struktur teks, dan reputasi sumber). Dibangun dengan Flask + vanilla JS, tanpa dependency yang rumit.

> **Penting:** CermatKuy memberikan **analisis awal**, bukan keputusan fakta yang absolut. Hasilnya tetap perlu diverifikasi lebih lanjut ke sumber resmi atau lembaga pemeriksa fakta.

---

## Fitur

- Input berupa **teks berita langsung** atau **URL artikel**.
- Ekstraksi otomatis judul, domain, dan isi artikel dari URL (dengan pembersihan HTML dan proteksi SSRF dasar).
- Analisis lokal yang benar-benar dihitung dari teks (bukan skor acak):
  - Pola bahasa sensasional/ajakan menyebarkan (mis. "SEBARKAN", "RAHASIA", "WAJIB SHARE").
  - Rasio huruf kapital berlebihan.
  - Tanda baca berlebihan (`!!!`, `???`).
  - Pola kalimat clickbait.
  - Panjang & struktur teks (jumlah kata, kalimat, paragraf).
  - Reputasi domain terhadap daftar sumber yang dikenal (`data/trusted_sources.json`).
- Sistem scoring transparan (0–100) dengan lima komponen berbobot, dan **penyeimbangan bobot otomatis** ketika suatu komponen tidak memiliki data (misalnya input berupa teks tanpa URL, atau fact-check API belum aktif) — supaya komponen kosong tidak mengaburkan sinyal risiko yang sebenarnya terukur.
- Status hasil: `Kemungkinan Hoaks` / `Perlu Verifikasi` / `Valid`.
- Hasil yang *explainable*: skor, status, indikator positif, indikator risiko, alasan, dan rekomendasi verifikasi lanjutan.
- Arsitektur siap integrasi fact-check API eksternal (dinonaktifkan secara default, tidak pernah memalsukan hasil).
- UI modern, responsive (mobile/tablet/desktop), tema biru-putih-abu ala aplikasi fact-checking.

---

## Technology Stack

**Backend:** Python 3, Flask, Requests, BeautifulSoup4
**Frontend:** HTML5, TailwindCSS (CDN), JavaScript vanilla (Fetch API)

---

## Struktur Folder

```text
cermatkuy/
│
├── app.py                       # Flask app: routing, request/response, validasi
├── requirements.txt
├── README.md
│
├── services/
│   ├── __init__.py
│   ├── analyzer.py              # Engine analisis & scoring (inti "AI" lokal)
│   ├── article_extractor.py     # Fetch + parsing artikel dari URL
│   ├── source_checker.py        # Reputasi domain
│   └── fact_checker.py          # Abstraksi fact-check API eksternal (nonaktif by default)
│
├── utils/
│   ├── __init__.py
│   └── text_utils.py            # Helper teks & validasi/keamanan URL (anti-SSRF)
│
├── templates/
│   ├── index.html
│   └── error.html
│
├── static/
│   ├── js/app.js
│   └── css/style.css
│
└── data/
    └── trusted_sources.json     # Daftar domain sumber yang dikenal
```

---

## Instalasi & Menjalankan

### Requirements

```text
Python 3.10+
```

### Langkah instalasi

```bash
git clone <repository>
cd cermatkuy

python -m venv venv
```

Aktifkan virtual environment.

Windows:

```bash
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

Install dependency dan jalankan:

```bash
pip install -r requirements.txt
python app.py
```

Buka di browser:

```text
http://127.0.0.1:5000
```

---

## Cara Menggunakan

1. Pilih mode input: **Teks Berita** atau **URL Berita**.
2. Tempel teks (minimal 20 karakter) atau masukkan URL artikel (`http://` / `https://`).
3. Klik **Periksa Berita**.
4. Sistem menampilkan skor kepercayaan, status, daftar indikator (dengan alasan), dan rekomendasi verifikasi lanjutan — tanpa reload halaman.

### API

```text
POST /api/analyze
Content-Type: application/json

{ "type": "text", "content": "..." }
{ "type": "url",  "content": "https://..." }
```

Response sukses (ringkas):

```json
{
  "success": true,
  "score": 72,
  "status": "Valid",
  "summary": "...",
  "indicators": [ { "name": "...", "status": "good|warning|bad|neutral", "description": "..." } ],
  "positive_indicators": ["..."],
  "risk_indicators": ["..."],
  "recommendation": "...",
  "score_breakdown": { "...lima komponen beserta bobot..." },
  "article": { "title": "...", "domain": "...", "url": "...", "word_count": 540 }
}
```

Response gagal:

```json
{ "success": false, "message": "Pesan error" }
```

---

## Sistem Scoring

| Komponen              | Bobot dasar |
|------------------------|-------------|
| Source Reputation       | 25% |
| Language Pattern        | 25% |
| Sensationalism           | 20% |
| Text Structure           | 15% |
| Fact Check Evidence      | 15% |

`0` = risiko hoaks sangat tinggi, `100` = tingkat kepercayaan tinggi (`score = max(0, min(score, 100))`).

Jika **Source Reputation** (input teks tanpa URL) atau **Fact Check Evidence** (API belum aktif) tidak memiliki data nyata, bobotnya didistribusikan ulang secara proporsional ke komponen lain yang benar-benar terukur dari teks (Language Pattern, Sensationalism, Text Structure), bukan diisi nilai netral yang mengaburkan hasil.

Kategori hasil:

| Skor | Status |
|------|--------|
| 0–39 | Kemungkinan Hoaks |
| 40–69 | Perlu Verifikasi |
| 70–100 | Valid |

---

## Mengaktifkan Fact-Check API (Pengembangan Selanjutnya)

Secara default `FACT_CHECK_API_ENABLED = False` di `services/fact_checker.py`, dan aplikasi berjalan sepenuhnya dengan analisis heuristik lokal (tidak pernah membuat hasil fact-check palsu).

Untuk mengaktifkan integrasi nyata (mis. Google Fact Check Tools API, TurnBackHoax, atau layanan cek fakta lainnya):

1. Set `FACT_CHECK_API_ENABLED = True` di `services/fact_checker.py`.
2. Implementasikan `_query_external_api()` agar memanggil API sungguhan dan mengembalikan daftar klaim nyata dengan struktur `{"claim", "rating", "publisher", "url"}`.
3. Simpan API key melalui environment variable dan baca di dalam `_query_external_api()`.

---

## Contoh Pengujian

### Test 1 — Bahasa sangat sensasional

```text
BREAKING!!! SEBARKAN SEKARANG SEBELUM DIHAPUS!!! Media tidak akan memberitakan informasi ini!!!
```

Hasil: skor rendah, status **Kemungkinan Hoaks** — banyak pola bahasa sensasional, huruf kapital berlebihan, dan tanda baca berulang.

### Test 2 — Artikel berita netral

Teks berita bergaya normal (bahasa formal, tanpa ajakan menyebarkan, struktur kalimat lengkap).

Hasil: skor tinggi, status **Valid** — tidak ditemukan indikator risiko kuat.

### Test 3 — Domain belum dikenal + bahasa sedikit sensasional

Teks dari sumber yang belum ada dalam daftar domain dikenal, dikombinasikan dengan sedikit bahasa sensasional.

Hasil: skor menengah, status **Perlu Verifikasi** — domain belum teridentifikasi bukan berarti hoaks, tetapi tetap perlu verifikasi tambahan bila digabung dengan indikator lain.

Skor tidak pernah di-hardcode berdasarkan contoh di atas; semua dihitung dari fungsi analisis di `services/analyzer.py`.

---

## Keterbatasan Versi Awal

- Analisis berbasis heuristik pola bahasa & statistik teks, bukan model machine learning yang dilatih pada data berlabel — cocok sebagai *first-pass filter*, bukan pengganti fact-checker manusia.
- Daftar domain terpercaya (`data/trusted_sources.json`) masih terbatas dan perlu terus diperbarui.
- Fact-check API eksternal belum terhubung (nonaktif secara default).
- Deteksi pola bahasa saat ini difokuskan pada Bahasa Indonesia.
- Ekstraksi artikel bergantung pada struktur HTML halaman sumber; sebagian situs dengan proteksi anti-bot atau rendering JavaScript penuh mungkin gagal diekstrak.

## Rekomendasi Pengembangan Berikutnya

- Integrasi nyata dengan Google Fact Check Tools API / basis data pemeriksa fakta lokal.
- Perluasan daftar sumber terpercaya dan kategori sumber (misalnya sumber pemerintah, media daerah).
- Model klasifikasi berbasis machine learning terlatih pada data berlabel Bahasa Indonesia sebagai pelengkap heuristik.
- Reverse image search untuk memeriksa foto/video yang digunakan di luar konteks.
- Riwayat pemeriksaan (opsional, tanpa sistem login) untuk transparansi audit.

---

## Keamanan

- Validasi input teks (tidak boleh kosong, minimal 20 karakter, dibatasi ukuran maksimum).
- Validasi URL (`http`/`https` saja) dan proteksi dasar SSRF: menolak akses ke `localhost`, `127.0.0.1`, `0.0.0.0`, `::1`, serta alamat IP privat/reserved (termasuk saat terjadi redirect).
- Batas ukuran request (`MAX_CONTENT_LENGTH`) dan timeout permintaan HTTP ke artikel eksternal.
- Escape output di sisi frontend (tidak ada `innerHTML` dari teks pengguna secara langsung).
- Traceback tidak ditampilkan ke pengguna; error production dikembalikan sebagai pesan JSON yang konsisten.

---

© 2026 CermatKuy
