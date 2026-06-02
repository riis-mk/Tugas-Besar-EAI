# Laporan Tugas Besar — Integrasi Aplikasi Enterprise
**Mata Kuliah:** Integrasi Aplikasi Enterprise  
**Judul Proyek:** SIAKAD × Keuangan × Perpustakaan — Integrasi Event-Driven Berbasis RabbitMQ  

---

## 1. Gaya Integrasi yang Dipilih & Alasannya

### Gaya: Message-Driven / Event-Driven Architecture (EDA)

Proyek ini menggunakan gaya **Message-Driven Integration** dengan **RabbitMQ** sebagai message broker. Setiap sistem mandiri (SIAKAD, Keuangan, Perpustakaan) berjalan secara independen; komunikasi antar sistem dimediasi sepenuhnya oleh **Integration Layer** yang berlangganan event dari message broker.

**Alasan pemilihan:**

| Faktor | Justifikasi |
|--------|------------|
| **Loose coupling** | Perpustakaan tidak perlu mengetahui keberadaan SIAKAD atau Keuangan. Ia hanya mempublikasikan event ke broker. |
| **Heterogenitas protokol** | Keuangan menggunakan SOAP/XML (Spyne), SIAKAD menggunakan REST/JSON. EDA memungkinkan Integration Layer menjembatani keduanya tanpa mengubah masing-masing sistem. |
| **Asinkronisitas** | Event `book.return.late` diproses secara asinkron: respons HTTP ke klien tidak terblokir oleh proses downstream. |
| **Skalabilitas** | Consumer dapat dijalankan dalam beberapa instance secara paralel tanpa modifikasi pada sistem sumber. |
| **Auditabilitas** | Dead-Letter Queue menampung pesan gagal untuk inspeksi manual, mendukung observabilitas integrasi. |

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
  "timestamp":  "2025-06-02T08:30:00+00:00",
  "student":    { "id": "...", "nim": "102022400067", "name": "Paris" },
  "book":       { "id": "...", "title": "Pengantar EAI", "isbn": "978-..." },
  "loan":       { "id": "...", "due_date": "2025-05-15", "return_date": "2025-06-02",
                  "overdue_days": 18, "fee_per_day": "5000.0", "total_fee": "90000.0", "currency": "IDR" }
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

**Mekanisme:** Objek CDM dikonversi menjadi SOAP 1.1 Envelope XML menggunakan `lxml` (bukan string templating). Namespace `http://keuangan.eai.university/soap` dan `http://schemas.xmlsoap.org/soap/envelope/` ditangani secara programatik.

**Envelope yang dihasilkan:**
```xml
<?xml version='1.0' encoding='UTF-8'?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:tns="http://keuangan.eai.university/soap">
  <soapenv:Header/>
  <soapenv:Body>
    <tns:CreateFine>
      <studentNim>102022400067</studentNim>
      <studentName>Paris</studentName>
      <loanId>c3d4e5f6-...</loanId>
      <bookTitle>Pengantar EAI</bookTitle>
      <totalFee>90000.0</totalFee>
      <overdueDays>18</overdueDays>
      <currency>IDR</currency>
    </tns:CreateFine>
  </soapenv:Body>
</soapenv:Envelope>
```

**Justifikasi:** Penggunaan `lxml` mencegah kesalahan escaping karakter XML (&, <, >) pada nilai dinamis seperti judul buku.

---

### 2.5 Content-Based Router

**Lokasi:** `integration-layer/app/router.py`

**Mekanisme:** Field `event_type` dalam CDM diperiksa; saat ini satu-satunya rute adalah `book.return.late → _handle_late_return()`. Fungsi handler mengorkestrasikan panggilan ke Keuangan (SOAP) lalu ke SIAKAD (REST) secara berurutan.

**Justifikasi:** Memisahkan keputusan routing dari logika pemrosesan. Penambahan event type baru (misalnya `book.lost`) hanya membutuhkan satu `elif` baru dan sebuah handler — zero change pada consumer atau translator.

---

### 2.6 Dead-Letter Queue (DLQ)

**Lokasi:** `integration-layer/app/consumer.py`

**Mekanisme:** `library.events.queue` dikonfigurasi dengan `x-dead-letter-exchange: library.dlx`. Pesan yang di-reject (payload malformed atau sudah diulang sekali tapi masih gagal) dialihkan ke `library.dlq` untuk audit manual. Strategi retry: satu kali requeue; gagal lagi → DLQ.

**Justifikasi:** Tanpa DLQ, pesan bermasalah akan me-loop selamanya di queue (infinite retry) dan memblokir pemrosesan pesan valid di belakangnya.

---

## 3. Mapping & Transformasi Data

### 3.1 Alur Transformasi End-to-End

```
Perpustakaan (FastAPI)
    │  domain event Python object
    ▼
publisher.py
    │  serialize → JSON bytes
    ▼
RabbitMQ (AMQP)
    │  routing_key: book.return.late
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
    ▼
cdm_to_soap.py  [Message Translator ②]
    │  CDM → SOAP 1.1 XML (lxml)
    │  Mapping: student.nim → <studentNim>, loan.total_fee → <totalFee>, dll.
    ▼
keuangan_client.py
    │  POST /soap (HTTP/1.1, Content-Type: text/xml)
    │  Parse response → ekstrak CreateFineResult (fine_id)
    ▼
siakad_client.py
    │  PATCH /students/{nim}/status
    │  Body: {"status":"SUSPENDED","reason":"..."}
    ▼
SIAKAD (FastAPI) — mahasiswa ter-suspend
```

### 3.2 Penanganan Heterogenitas

| Aspek | Perpustakaan | Keuangan | SIAKAD |
|-------|-------------|---------|--------|
| Protokol | AMQP (publish) | SOAP 1.1 / HTTP | REST / HTTP |
| Format data | JSON | XML | JSON |
| Database | PostgreSQL | MySQL | PostgreSQL |
| Framework | FastAPI | Flask + Spyne | FastAPI |
| Tipe `total_fee` | `str` dalam JSON | `Numeric(15,2)` MySQL | — |

Semua konversi tipe dan format ditangani di Integration Layer. Masing-masing sistem mandiri tidak mengetahui format sistem lain.

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

**Masalah:** `total_fee` dalam payload JSON Perpustakaan dikirim sebagai string (`"50000.0"`). Spyne mendefinisikan parameter `totalFee` sebagai `Unicode`, sehingga nilai ini tiba di Keuangan sebagai string. Kolom MySQL menggunakan `Numeric(15,2)`.

**Solusi:** SQLAlchemy secara otomatis melakukan koersi string → Decimal saat insert ke kolom `Numeric`. Tidak diperlukan konversi manual. Di sisi CDM, `total_fee` disimpan sebagai `Decimal` setelah `json_to_cdm.py` melakukan `Decimal(str(loan_raw["total_fee"]))`.

---

## 6. Kesimpulan

Proyek ini berhasil mengimplementasikan integrasi **event-driven** antara tiga sistem mandiri (Perpustakaan, Keuangan, SIAKAD) menggunakan **6 Enterprise Integration Patterns**: Publish-Subscribe, Message Translator (×2), Canonical Data Model, Content-Based Router, dan Dead-Letter Queue. 

Arsitektur yang dipilih memenuhi syarat *loose coupling* — setiap sistem tidak mengetahui keberadaan sistem lain dan menggunakan database yang sepenuhnya terpisah (2× PostgreSQL, 1× MySQL). Seluruh orkestrasi dilakukan oleh Integration Layer yang berperan sebagai mediator. Sistem dapat dijalankan dengan satu perintah (`docker compose up --build`) dan alur integrasi end-to-end (keterlambatan pengembalian buku → denda Keuangan → suspensi SIAKAD) dapat diverifikasi dalam hitungan detik.
