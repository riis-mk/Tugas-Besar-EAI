# Laporan Tugas Besar — Integrasi Aplikasi Enterprise
**Mata Kuliah:** Integrasi Aplikasi Enterprise  
**Judul Proyek:** SIAKAD × Keuangan × Perpustakaan Integrasi Event-Driven Berbasis RabbitMQ 
**Anggota Kelompok :**

**NIM:** 102022400067 **Nama** Paris

**NIM:** 102022400046 **Nama** Jazman Jati Muhtadi

---

## 1. Gaya Integrasi yang Dipilih & Alasannya

### Gaya: Message-Driven / Event-Driven Architecture (EDA)

Proyek ini menggunakan gaya **Message-Driven Integration** dengan **RabbitMQ** sebagai message broker. Setiap sistem mandiri (SIAKAD, Keuangan, Perpustakaan) berjalan secara independen; komunikasi antar sistem dimediasi sepenuhnya oleh **Integration Layer** yang berlangganan event dari message broker.

Selain komunikasi event-driven, terdapat juga **integrasi sinkron langsung** antara Perpustakaan dan SIAKAD: Perpustakaan tidak memiliki basis data mahasiswa sendiri melainkan mengambil data mahasiswa secara langsung dari SIAKAD melalui REST API setiap kali diperlukan. Ini menjadikan SIAKAD sebagai **sumber data otoritatif (single source of truth)** untuk informasi mahasiswa.

**Alasan pemilihan:**

| Faktor | Justifikasi |
|--------|------------|
| **Loose coupling** | Perpustakaan tidak perlu mengelola registrasi mahasiswa secara mandiri. Ia hanya mengambil data dari SIAKAD dan mempublikasikan event ke broker. |
| **Heterogenitas protokol** | Keuangan menggunakan SOAP/XML (Spyne), SIAKAD menggunakan REST/JSON. EDA memungkinkan Integration Layer menjembatani keduanya tanpa mengubah masing-masing sistem. |
| **Asinkronisitas** | Event `book.return.late` diproses secara asinkron: respons HTTP ke klien tidak terblokir oleh proses downstream. |
| **Skalabilitas** | Consumer dapat dijalankan dalam beberapa instance secara paralel tanpa modifikasi pada sistem sumber. |
| **Auditabilitas** | Dead-Letter Queue menampung pesan gagal untuk inspeksi manual, mendukung observabilitas integrasi. |
| **Single source of truth** | Data mahasiswa dikelola sepenuhnya oleh SIAKAD; Perpustakaan hanya menyimpan cache lokal yang disinkronkan on-demand. |

---

## 2. Pola EIP yang Diterapkan & Justifikasi

### 2.1 Publish-Subscribe

**Lokasi:** `perpustakaan/app/publisher.py` (publisher) + `integration-layer/app/consumer.py` (subscriber)

**Mekanisme:** Perpustakaan mempublikasikan event JSON ke **topic exchange** `library.exchange` dengan routing key `book.return.late`. Integration Layer terikat ke exchange tersebut melalui queue `library.events.queue` dengan binding pattern `book.return.#`.

**Justifikasi:** Topic exchange memungkinkan lebih dari satu subscriber di masa depan (misalnya, sistem notifikasi email atau SMS) tanpa perubahan pada publisher. Ini adalah implementasi EIP *Publish-Subscribe Channel* yang tepat untuk event domain.

**Payload yang dipublikasikan:**
```json
{
  "event_id":   "f47ac10b-...",
  "event_type": "book.return.late",
  "timestamp":  "2026-06-11T03:29:58+00:00",
  "student":    { "id": "...", "nim": "2024001", "name": "Budi Santoso" },
  "book":       { "id": "...", "title": "Pemrograman Python Modern", "isbn": "978-602-12345-1" },
  "loan":       { "id": "...", "due_date": "2026-05-15", "return_date": "2026-06-11",
                  "overdue_days": 27, "fee_per_day": "5000.0", "total_fee": "135000.0", "currency": "IDR" }
}
```

---

### 2.2 Message Translator (JSON → CDM)

**Lokasi:** `integration-layer/app/translators/json_to_cdm.py`

**Mekanisme:** Byte JSON mentah dari RabbitMQ dikonversi menjadi objek **Canonical Data Model** (CDM) menggunakan Pydantic. Seluruh parsing, koersi tipe (`Decimal`, `datetime`), dan validasi lapangan dilakukan di sini.

**Justifikasi:** Memisahkan format kawat (wire format) dari logika bisnis. Jika Perpustakaan mengubah nama field, hanya translator yang perlu dimodifikasi, bukan router atau client.

---

### 2.3 Canonical Data Model (CDM)

**Lokasi:** `integration-layer/app/cdm/models.py`

**Mekanisme:** Kelas Pydantic `LateFeeEventCDM`, `StudentCDM`, `BookCDM`, `LoanCDM` mendefinisikan representasi data netral teknologi. Baik JSON maupun SOAP XML ditransformasi ke/dari CDM ini.

**Justifikasi:** Tanpa CDM, setiap pasang sistem membutuhkan transformasi langsung (*point-to-point*) yang menghasilkan kompleksitas O(n²). CDM menguranginya menjadi O(n) — setiap sistem hanya perlu satu translator ke/dari CDM.

---

### 2.4 Message Translator (CDM → SOAP/XML)

**Lokasi:** `integration-layer/app/translators/cdm_to_soap.py`

**Mekanisme:** Objek CDM dikonversi menjadi SOAP 1.1 Envelope XML menggunakan `lxml` (bukan string templating). Namespace `http://keuangan.eai.university/soap` diterapkan secara eksplisit pada seluruh elemen di dalam body operasi, termasuk elemen-elemen parameter.

**Envelope yang dihasilkan:**
```xml
<?xml version='1.0' encoding='UTF-8'?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:tns="http://keuangan.eai.university/soap">
  <soapenv:Header/>
  <soapenv:Body>
    <tns:CreateFine>
      <tns:studentNim>2024001</tns:studentNim>
      <tns:studentName>Budi Santoso</tns:studentName>
      <tns:loanId>f853a241-...</tns:loanId>
      <tns:bookTitle>Pemrograman Python Modern</tns:bookTitle>
      <tns:totalFee>135000.0</tns:totalFee>
      <tns:overdueDays>27</tns:overdueDays>
      <tns:currency>IDR</tns:currency>
    </tns:CreateFine>
  </soapenv:Body>
</soapenv:Envelope>
```

**Justifikasi:** Penggunaan `lxml` mencegah kesalahan escaping karakter XML (&, <, >) pada nilai dinamis seperti judul buku. Penerapan namespace TNS pada setiap elemen parameter diperlukan agar Spyne `lxml` validator menerima envelope tanpa error skema.

---

### 2.5 Content-Based Router

**Lokasi:** `integration-layer/app/router.py`

**Mekanisme:** Field `event_type` dalam CDM diperiksa; saat ini satu-satunya rute adalah `book.return.late → _handle_late_return()`. Fungsi handler mengorkestrasikan tiga langkah secara berurutan:

1. **Keuangan** — buat tagihan denda via SOAP
2. **SIAKAD** — catat utang perpustakaan (`PATCH /students/{nim}/library-debt`)
3. **SIAKAD** — suspensi status akademik (`PATCH /students/{nim}/status`) ← hanya jika langkah 1 berhasil

**Justifikasi:** Memisahkan keputusan routing dari logika pemrosesan. Penambahan event type baru hanya membutuhkan satu `elif` baru dan sebuah handler — zero change pada consumer atau translator. Pencatatan utang dilakukan sebelum suspensi agar data finansial tersimpan meskipun proses suspensi gagal.

---

### 2.6 Dead-Letter Queue (DLQ)

**Lokasi:** `integration-layer/app/consumer.py`

**Mekanisme:** `library.events.queue` dikonfigurasi dengan `x-dead-letter-exchange: library.dlx`. Pesan yang di-reject (payload malformed atau sudah diulang sekali tapi masih gagal) dialihkan ke `library.dlq` untuk audit manual. Strategi retry: satu kali requeue; gagal lagi → DLQ.

**Justifikasi:** Tanpa DLQ, pesan bermasalah akan me-loop selamanya di queue (infinite retry) dan memblokir pemrosesan pesan valid di belakangnya.

---

## 3. Mapping & Transformasi Data

### 3.1 Alur Transformasi End-to-End

```
[SINKRON] Peminjaman Buku
─────────────────────────────────────────────────
Klien → POST /loans (student_nim)
            │
            ▼
    perpustakaan/loans.py
            │  Cek cache lokal mahasiswa
            │  Tidak ada? → GET http://siakad:8000/students/{nim}
            │               Simpan ke cache lokal
            ▼
    Peminjaman berhasil dibuat


[ASINKRON] Pengembalian Terlambat
─────────────────────────────────────────────────
Perpustakaan (FastAPI)
    │  domain event Python object
    ▼
publisher.py
    │  serialize → JSON bytes
    ▼
RabbitMQ (AMQP) — routing_key: book.return.late
    ▼
consumer.py (pika)
    │  raw bytes
    ▼
json_to_cdm.py  [Message Translator ①]
    │  JSON → LateFeeEventCDM (Pydantic)
    │  Konversi: fee_per_day/total_fee → Decimal
    │             due_date/return_date → datetime
    ▼
router.py  [Content-Based Router]
    │  route by event_type
    ├─► cdm_to_soap.py  [Message Translator ②]
    │       │  CDM → SOAP 1.1 XML (lxml, dengan TNS namespace)
    │       ▼
    │   keuangan_client.py
    │       │  POST /soap → fine_id
    │
    ├─► siakad_client.update_library_debt()
    │       │  PATCH /students/{nim}/library-debt
    │       │  Body: {"amount": 135000.0, "notes": "...detail denda..."}
    │
    └─► siakad_client.suspend_student()
            │  PATCH /students/{nim}/status
            │  Body: {"status": "SUSPENDED", "reason": "..."}
            ▼
        SIAKAD — mahasiswa ter-suspend + utang perpustakaan tercatat
```

### 3.2 Penanganan Heterogenitas

| Aspek | Perpustakaan | Keuangan | SIAKAD |
|-------|-------------|---------|--------|
| Protokol | AMQP (publish) + REST (consume dari SIAKAD) | SOAP 1.1 / HTTP | REST / HTTP |
| Format data | JSON | XML | JSON |
| Database | PostgreSQL | MySQL | PostgreSQL |
| Framework | FastAPI | Flask + Spyne | FastAPI |
| Tipe `total_fee` | `str` dalam JSON | `Numeric(15,2)` MySQL | `Float` PostgreSQL |
| Data mahasiswa | Cache lokal (sync dari SIAKAD) | — | Master / Sumber Otoritatif |

Semua konversi tipe dan format ditangani di Integration Layer. Masing-masing sistem mandiri tidak mengetahui format sistem lain.

### 3.3 Struktur Data SIAKAD (setelah integrasi)

Tabel `students` di SIAKAD kini menyimpan informasi utang perpustakaan yang diupdate oleh Integration Layer:

```json
{
  "id": "c24f179c-...",
  "nim": "102022400046",
  "name": "Jazman",
  "academic_status": "SUSPENDED",
  "program_studi": "Sistem Informasi",
  "angkatan": "2024",
  "library_debt": 135000.0,
  "library_debt_notes": "[2026-06-11] Keterlambatan pengembalian buku \"Pemrograman Python Modern\" selama 27 hari. Denda: IDR 135000.0. Ref tagihan: 0cc2c5e3-..."
}
```

---

## 4. Pembagian Tugas

| Komponen | Penanggung Jawab |
|----------|-----------------|
| Perpustakaan (FastAPI + PostgreSQL + Publisher) | Seluruh Tim |
| Keuangan (Flask + Spyne SOAP + MySQL) | Seluruh Tim |
| SIAKAD (FastAPI + PostgreSQL) | Seluruh Tim |
| Integration Layer (consumer, router, translators, clients) | Seluruh Tim |
| Docker Compose & infrastruktur | Seluruh Tim |
| Dokumentasi (README, laporan, diagram) | Seluruh Tim |

---

## 5. Kendala & Solusi

### Kendala 1: Spyne SOAP + Waitress + Flask DispatcherMiddleware

**Masalah:** Menjalankan Spyne `WsgiApplication` berdampingan dengan Flask di port yang sama memerlukan middleware dispatcher. Konfigurasi `Waitress` sebagai WSGI server produksi untuk kedua aplikasi sekaligus tidak langsung tersedia.

**Solusi:** Menggunakan `werkzeug.middleware.dispatcher.DispatcherMiddleware` untuk me-mount Spyne di path `/soap` dan Flask sebagai root. Seluruh aplikasi WSGI gabungan kemudian dilayani oleh `waitress.serve()`.

---

### Kendala 2: Dead-Letter Queue — namespace routing key

**Masalah:** Pesan yang di-nack tidak masuk ke DLQ karena routing key dead-letter tidak cocok dengan binding di DLX.

**Solusi:** Menambahkan `x-dead-letter-routing-key: library.dead` secara eksplisit pada deklarasi queue, dan memastikan `queue_bind` pada DLQ menggunakan routing key yang sama (`library.dead`), bukan `#` atau string kosong.

---

### Kendala 3: Race condition — Integration Layer start sebelum Keuangan siap

**Masalah:** Saat `docker compose up`, `integration_layer` container terkadang mencoba terhubung ke RabbitMQ sebelum deklarasi topology selesai atau ke Keuangan sebelum Waitress menerima koneksi.

**Solusi:** Menambahkan logika reconnect loop di `consumer.py`: koneksi AMQP diulang setiap 5 detik jika gagal. Untuk Keuangan dan SIAKAD, `keuangan_client.py` dan `siakad_client.py` menggunakan `requests` dengan timeout, dan exception dari downstream menyebabkan `basic_nack` (requeue) sehingga pesan tidak hilang selama downstream sedang startup.

---

### Kendala 4: Heterogenitas tipe data `total_fee`

**Masalah:** `total_fee` dalam payload JSON Perpustakaan dikirim sebagai string (`"135000.0"`). Spyne mendefinisikan parameter `totalFee` sebagai `Unicode`, sehingga nilai ini tiba di Keuangan sebagai string. Kolom MySQL menggunakan `Numeric(15,2)`.

**Solusi:** SQLAlchemy secara otomatis melakukan koersi string → Decimal saat insert ke kolom `Numeric`. Tidak diperlukan konversi manual. Di sisi CDM, `total_fee` disimpan sebagai `Decimal` setelah `json_to_cdm.py` melakukan `Decimal(str(loan_raw["total_fee"]))`.

---

### Kendala 5: Namespace TNS pada elemen SOAP — Spyne schema validation error

**Masalah:** Spyne dikonfigurasi dengan `Soap11(validator="lxml")` yang melakukan validasi XSD ketat terhadap SOAP envelope yang masuk. Elemen-elemen parameter di dalam `<tns:CreateFine>` (seperti `<studentNim>`, `<totalFee>`) dibangun tanpa namespace, sehingga Spyne menolaknya dengan error:

```
soap11env:Client.SchemaValidationError: Element 'studentNim': This element is not expected.
Expected is one of ( {http://keuangan.eai.university/soap}studentNim, ... )
```

**Solusi:** Memperbaiki `integration-layer/app/translators/cdm_to_soap.py` — setiap elemen parameter dibuat dengan namespace TNS eksplisit menggunakan `f"{{{TNS}}}{tag}"`:

```python
# Sebelum (salah):
child = etree.SubElement(op, tag)

# Sesudah (benar):
child = etree.SubElement(op, f"{{{TNS}}}{tag}")
```

---

### Kendala 6: Data mahasiswa tidak sinkron antara Perpustakaan dan SIAKAD

**Masalah:** Perpustakaan sebelumnya memiliki tabel dan endpoint registrasi mahasiswa sendiri (`POST /students`). Ini menyebabkan duplikasi data — mahasiswa harus didaftarkan dua kali (ke SIAKAD dan ke Perpustakaan secara terpisah) dan keduanya bisa tidak sinkron jika NIM berbeda atau salah satu terlewat.

**Solusi:** Menghapus endpoint `POST /students` dari Perpustakaan. Sebagai gantinya:
- Saat `POST /loans` dibuat, Perpustakaan mencari mahasiswa di cache lokal terlebih dahulu.
- Jika tidak ada, Perpustakaan memanggil `GET http://siakad:8000/students/{nim}` secara sinkron.
- Data mahasiswa dari SIAKAD disimpan ke cache lokal Perpustakaan secara otomatis.
- Jika NIM tidak ditemukan di SIAKAD, peminjaman ditolak dengan error 404.

Ditambahkan `SIAKAD_REST_URL` sebagai environment variable di `docker-compose.yml` untuk service perpustakaan, serta dependensi `requests==2.32.3` di `perpustakaan/requirements.txt`.

---

### Kendala 7: Informasi utang perpustakaan tidak terlihat di SIAKAD

**Masalah:** Setelah mahasiswa dikenai denda akibat keterlambatan pengembalian buku, informasi denda hanya tersimpan di Keuangan. SIAKAD hanya tahu bahwa mahasiswa di-suspend, tetapi tidak tahu berapa total utangnya ke perpustakaan maupun detail bukunya.

**Solusi:** Menambahkan dua kolom baru pada tabel `students` di SIAKAD:
- `library_debt` (Float) — total akumulasi utang perpustakaan dalam IDR
- `library_debt_notes` (Text) — riwayat catatan denda (append, bukan replace)

Integration Layer kini memanggil endpoint baru `PATCH /students/{nim}/library-debt` di SIAKAD sebagai langkah kedua dalam alur `_handle_late_return()`, sebelum melakukan suspensi. Endpoint ini menambahkan jumlah denda ke total utang dan mengappend catatan denda ke riwayat.

---

## 6. Kesimpulan

Proyek ini berhasil mengimplementasikan integrasi **event-driven** antara tiga sistem mandiri (Perpustakaan, Keuangan, SIAKAD) menggunakan **6 Enterprise Integration Patterns**: Publish-Subscribe, Message Translator (×2), Canonical Data Model, Content-Based Router, dan Dead-Letter Queue.

Arsitektur yang dipilih memenuhi syarat *loose coupling* — setiap sistem tidak mengetahui keberadaan sistem lain dan menggunakan database yang sepenuhnya terpisah (2× PostgreSQL, 1× MySQL). Seluruh orkestrasi dilakukan oleh Integration Layer yang berperan sebagai mediator.

Integrasi diperkuat dengan menjadikan **SIAKAD sebagai sumber data otoritatif** untuk mahasiswa: Perpustakaan tidak lagi memiliki registrasi mandiri melainkan mengambil data langsung dari SIAKAD on-demand. Selain itu, SIAKAD kini mencerminkan **kondisi lengkap mahasiswa** — bukan hanya status akademik, tetapi juga total utang perpustakaan beserta riwayat dendanya — sehingga pengelola akademik dapat melihat gambaran penuh dari satu sistem.

Alur integrasi end-to-end yang telah diverifikasi:

```
Mahasiswa terdaftar di SIAKAD
    ↓
Perpustakaan pinjam buku → auto-fetch data mahasiswa dari SIAKAD
    ↓ (jika terlambat dikembalikan)
Event book.return.late → RabbitMQ
    ↓
Integration Layer:
    1. Keuangan (SOAP): buat tagihan denda → fine_id
    2. SIAKAD (REST): catat utang perpustakaan +IDR 135.000
    3. SIAKAD (REST): suspensi status akademik → SUSPENDED
```

Sistem dapat dijalankan dengan satu perintah (`docker compose up --build`) dan seluruh alur di atas dapat diverifikasi dalam hitungan detik.
