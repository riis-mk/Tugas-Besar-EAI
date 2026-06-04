# SIAKAD × Keuangan × Perpustakaan — Integrasi Event-Driven Berbasis RabbitMQ

> Tugas Besar Mata Kuliah **Integrasi Aplikasi Enterprise** — Semester 4

**Anggota Kelompok:**

| NIM | Nama |
|-----|------|
| 102022400067 | Paris |
| 102022400046 | Jazman Jati Muhtadi |

Proyek ini mengintegrasikan tiga sistem informasi kampus yang heterogen menggunakan arsitektur *event-driven* berbasis **RabbitMQ** dan pola-pola **Enterprise Integration Patterns (EIP)**.

> **Dokumen pendukung:** [proposal.md](proposal.md) — tema, daftar aplikasi & format data, diagram arsitektur | [spesifikasi.md](spesifikasi.md) — spesifikasi teknis | [laporan.md](laporan.md) — laporan EIP & transformasi data

---

## Arsitektur Sistem

```
┌─────────────────────────────────────────────────────────────────────┐
│  Sistem Mandiri (Bounded Context)                                   │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Perpustakaan    │  │    Keuangan       │  │     SIAKAD       │  │
│  │  FastAPI :8001   │  │  Flask+Spyne :8002│  │  FastAPI :8003   │  │
│  │  PostgreSQL      │  │  MySQL            │  │  PostgreSQL      │  │
│  └────────┬─────────┘  └────────▲──────────┘  └────────▲─────────┘  │
└───────────┼──────────────────────┼────────────────────────┼──────────┘
            │ Publish-Subscribe    │ SOAP/XML               │ REST/JSON
            │ JSON event           │ (Message Translator)   │ (Message Translator)
            ▼                      │                        │
┌──────────────────────────────────┼────────────────────────┼──────────┐
│  RabbitMQ (library.exchange)     │                        │          │
│   routing_key: book.return.late  │                        │          │
│                ▼                 │                        │          │
│   library.events.queue           │                        │          │
│         ↓ (on reject)            │                        │          │
│   library.dlq (Dead-Letter)      │                        │          │
└────────────────┬─────────────────┼────────────────────────┼──────────┘
                 │ consume          │                        │
                 ▼                 │                        │
┌────────────────────────────────────────────────────────────────────┐
│  Integration Layer (Pure Python / pika)                            │
│                                                                    │
│  [1] Message Translator: JSON raw bytes → Canonical Data Model     │
│  [2] Content-Based Router: dispatch by event_type                  │
│  [3] Message Translator: CDM → SOAP 1.1 Envelope (XML)            │
│       └→ POST /soap ──────────────────────────────────────────────►│
│  [4] REST call: PATCH /students/{nim}/status ─────────────────────►│
└────────────────────────────────────────────────────────────────────┘
```

Sistem bekerja sepenuhnya *loosely coupled*: setiap aplikasi tidak mengetahui keberadaan aplikasi lain. Seluruh orkestrasi dilakukan oleh **Integration Layer** yang mengonsumsi event dari RabbitMQ.

---

## Daftar Sistem & Endpoint

### 1. Perpustakaan (`localhost:8001`)

| Method | Path | Deskripsi |
|--------|------|-----------|
| `POST` | `/students/` | Daftarkan mahasiswa ke sistem perpustakaan |
| `GET` | `/students/{nim}` | Detail mahasiswa di sistem perpustakaan |
| `POST` | `/books/` | Tambah buku baru |
| `GET` | `/books/` | Daftar semua buku |
| `GET` | `/books/{book_id}` | Detail buku |
| `POST` | `/loans/` | Buat transaksi peminjaman (gunakan `student_nim`) |
| `PATCH` | `/loans/{loan_id}/return` | Kembalikan buku — **memicu event RabbitMQ jika terlambat** |

> Dokumentasi interaktif: `http://localhost:8001/docs`

### 2. Keuangan (`localhost:8002`)

| Method | Path | Deskripsi |
|--------|------|-----------|
| `POST` | `/soap` | Endpoint SOAP 1.1 — operasi `CreateFine` |
| `GET` | `/soap?wsdl` | WSDL descriptor layanan |

> Dikonsumsi **hanya** oleh Integration Layer; tidak dimaksudkan untuk dipanggil langsung oleh klien akhir.

### 3. SIAKAD (`localhost:8003`)

| Method | Path | Deskripsi |
|--------|------|-----------|
| `POST` | `/students/` | Tambah data mahasiswa |
| `GET` | `/students/{nim}` | Detail mahasiswa |
| `PATCH` | `/students/{nim}/status` | Perbarui status akademik (ACTIVE / SUSPENDED / GRADUATED) |

> Dokumentasi interaktif: `http://localhost:8003/docs`

### 4. RabbitMQ Management UI

| URL | Kredensial |
|-----|-----------|
| `http://localhost:15672` | `admin` / `admin_r4bbit_secret` |

---

## Format Pertukaran Data

### JSON — Event dari Perpustakaan ke RabbitMQ

Dipublikasikan ke exchange `library.exchange` dengan routing key `book.return.late`.

```json
{
  "event_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "event_type": "book.return.late",
  "timestamp": "2025-06-02T08:30:00+00:00",
  "student": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "nim": "102022400067",
    "name": "Paris"
  },
  "book": {
    "id": "b9c8d7e6-f5a4-3210-fedc-ba9876543210",
    "title": "Pengantar Sistem Informasi Enterprise",
    "isbn": "978-602-1234-56-7"
  },
  "loan": {
    "id": "c3d4e5f6-a7b8-9012-3456-789012345678",
    "due_date": "2025-05-23T00:00:00",
    "return_date": "2025-06-02T00:00:00",
    "overdue_days": 10,
    "fee_per_day": "5000.0",
    "total_fee": "50000.0",
    "currency": "IDR"
  }
}
```

### XML — SOAP Envelope dari Integration Layer ke Keuangan

Dihasilkan oleh **Message Translator** (CDM → SOAP) menggunakan `lxml`, dikirim via `POST /soap`.

```xml
<?xml version='1.0' encoding='UTF-8'?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:tns="http://keuangan.eai.university/soap">
  <soapenv:Header/>
  <soapenv:Body>
    <tns:CreateFine>
      <studentNim>102022400067</studentNim>
      <studentName>Paris</studentName>
      <loanId>c3d4e5f6-a7b8-9012-3456-789012345678</loanId>
      <bookTitle>Pengantar Sistem Informasi Enterprise</bookTitle>
      <totalFee>50000.0</totalFee>
      <overdueDays>10</overdueDays>
      <currency>IDR</currency>
    </tns:CreateFine>
  </soapenv:Body>
</soapenv:Envelope>
```

### JSON — REST call dari Integration Layer ke SIAKAD

```json
PATCH /students/102022400067/status

{
  "status": "SUSPENDED",
  "reason": "Keterlambatan pengembalian buku \"Pengantar Sistem Informasi Enterprise\" selama 10 hari. Denda: IDR 50000.0. Referensi tagihan: <fine_id>."
}
```

---

## Topologi RabbitMQ

```
library.exchange (topic)
    └── binding: book.return.#
            ▼
    library.events.queue
        │
        └── x-dead-letter-exchange: library.dlx
                    ▼
            library.dlq  ← pesan gagal / ditolak permanen
```

| Komponen | Tipe | Keterangan |
|----------|------|-----------|
| `library.exchange` | topic | Publisher utama Perpustakaan |
| `library.events.queue` | durable queue | Antrian konsumsi Integration Layer |
| `library.dlx` | direct exchange | Dead-Letter Exchange |
| `library.dlq` | durable queue | Penampung pesan gagal untuk audit |

---

## Diagram Arsitektur (Mermaid)

```mermaid
flowchart TB
    subgraph PERP_SYS["Perpustakaan  :8001"]
        PERP_APP["FastAPI\nbooks / loans"]
        PG_PERP[("PostgreSQL")]
        PERP_APP <--> PG_PERP
    end

    subgraph KEU_SYS["Keuangan  :8002"]
        KEU_APP["Flask + Spyne\nSOAP :8002/soap"]
        MYSQL[("MySQL")]
        KEU_APP <--> MYSQL
    end

    subgraph SIA_SYS["SIAKAD  :8003"]
        SIA_APP["FastAPI\nstudents"]
        PG_SIA[("PostgreSQL")]
        SIA_APP <--> PG_SIA
    end

    subgraph BROKER["RabbitMQ  :5672"]
        EXCHANGE["library.exchange\n(topic)"]
        QUEUE["library.events.queue"]
        DLX["library.dlx"]
        DLQ["library.dlq\n⚰ Dead-Letter Queue"]
        EXCHANGE -->|"binding: book.return.#"| QUEUE
        QUEUE -->|"nack / reject"| DLX
        DLX --> DLQ
    end

    subgraph IL["Integration Layer"]
        CONSUMER["Consumer\npika"]
        MT1["① Message Translator\nJSON bytes → CDM"]
        CDM(["Canonical Data Model"])
        CBR{"② Content-Based Router\nevent_type dispatch"}
        MT2["③ Message Translator\nCDM → SOAP 1.1 XML"]
        CONSUMER --> MT1 --> CDM --> CBR
        CBR -->|"book.return.late"| MT2
    end

    PERP_APP -->|"① Publish-Subscribe\nrouting_key: book.return.late\nJSON"| EXCHANGE
    QUEUE -->|"consume"| CONSUMER
    MT2 -->|"POST /soap\nSOAP 1.1 / XML"| KEU_APP
    CBR -->|"PATCH /students/{nim}/status\nREST / JSON"| SIA_APP
```

---

## Cara Menjalankan dari Nol

### Prasyarat

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (versi 24+)
- Docker Compose v2 (sudah termasuk dalam Docker Desktop)

### Langkah-langkah

**1. Clone / ekstrak repositori**

```bash
cd "Semester 4/INTEGRASI APLIKASI ENTERPRISE/Tugas Besar"
```

**2. Salin konfigurasi environment**

File `.env` sudah tersedia di root repositori. Verifikasi isinya:

```bash
cat .env
```


**3. Bangun image dan jalankan seluruh layanan**

```bash
docker compose up --build -d
```

Docker Compose akan menjalankan layanan sesuai urutan `depends_on`:
1. `rabbitmq`, `postgres_perpustakaan`, `postgres_siakad`, `mysql_keuangan` (infrastruktur)
2. `perpustakaan`, `keuangan`, `siakad` (aplikasi, menunggu database *healthy*)
3. `integration_layer` (menunggu RabbitMQ + keuangan + siakad siap)

**4. Verifikasi semua kontainer berjalan**

```bash
docker compose ps
```

Semua layanan harus berstatus `running` atau `healthy`.

**5. Uji alur integrasi end-to-end**

```bash
# a) Tambah mahasiswa ke SIAKAD
curl -X POST http://localhost:8003/students/ \
  -H "Content-Type: application/json" \
  -d '{"nim":"102022400067","name":"Paris","program_studi":"Sistem Informasi","angkatan":"2022"}'

# b) Daftarkan mahasiswa yang sama ke sistem Perpustakaan
curl -X POST http://localhost:8001/students/ \
  -H "Content-Type: application/json" \
  -d '{"nim":"102022400067","name":"Paris"}'

# c) Tambah buku ke Perpustakaan
curl -X POST http://localhost:8001/books/ \
  -H "Content-Type: application/json" \
  -d '{"title":"Pengantar EAI","isbn":"978-000-0000-00-0","author":"Dosen EAI"}'

# Catat book_id dari respons langkah c

# d) Buat peminjaman (gunakan book_id dari langkah c, student_nim berupa NIM)
curl -X POST http://localhost:8001/loans/ \
  -H "Content-Type: application/json" \
  -d '{"book_id":"<book_id>","student_nim":"102022400067","loan_date":"2025-05-01","due_date":"2025-05-15"}'

# Catat loan_id dari respons

# e) Kembalikan buku TERLAMBAT — ini memicu event integrasi
curl -X PATCH http://localhost:8001/loans/<loan_id>/return \
  -H "Content-Type: application/json" \
  -d '{"return_date":"2025-06-02"}'
```

Setelah langkah (e), Integration Layer akan:
1. Menerima event `book.return.late` dari RabbitMQ
2. Membuat denda di Keuangan via SOAP
3. Menangguhkan status akademik mahasiswa di SIAKAD

```bash
# f) Verifikasi: cek status mahasiswa di SIAKAD
curl http://localhost:8003/students/102022400067
# academic_status harus menjadi "SUSPENDED"
```

**6. Melihat log Integration Layer secara real-time**

```bash
docker compose logs -f integration_layer
```

**7. Menghentikan semua layanan**

```bash
# Hentikan tanpa menghapus data volume
docker compose down

# Hentikan DAN hapus semua data (reset penuh)
docker compose down -v
```

---

## Struktur Direktori

```
.
├── docker-compose.yml
├── .env
├── perpustakaan/
│   ├── Dockerfile
│   └── app/
│       ├── main.py
│       ├── models.py
│       ├── publisher.py          ← EIP: Publish-Subscribe
│       └── routers/
│           ├── students.py
│           ├── books.py
│           └── loans.py
├── keuangan/
│   ├── Dockerfile
│   └── app/
│       ├── main.py
│       ├── models.py
│       └── soap_service.py       ← Spyne SOAP 1.1
├── siakad/
│   ├── Dockerfile
│   └── app/
│       ├── main.py
│       ├── models.py
│       └── routers/
│           └── students.py
└── integration-layer/
    ├── Dockerfile
    └── app/
        ├── main.py
        ├── consumer.py           ← EIP: Publish-Subscribe (consumer) + DLQ
        ├── router.py             ← EIP: Content-Based Router
        ├── cdm/
        │   └── models.py         ← Canonical Data Model
        ├── translators/
        │   ├── json_to_cdm.py    ← EIP: Message Translator (JSON → CDM)
        │   └── cdm_to_soap.py    ← EIP: Message Translator (CDM → SOAP/XML)
        └── clients/
            ├── keuangan_client.py
            └── siakad_client.py
```

---

## Pola EIP yang Diimplementasikan

| Pola | Lokasi | Deskripsi |
|------|--------|-----------|
| **Publish-Subscribe** | `perpustakaan/publisher.py` + `integration-layer/consumer.py` | Topic exchange memungkinkan beberapa subscriber di masa depan |
| **Message Translator** | `integration-layer/translators/` | JSON → CDM (normalisasi), CDM → SOAP 1.1 XML (transformasi) |
| **Content-Based Router** | `integration-layer/router.py` | Routing berdasarkan `event_type` dalam CDM |
| **Dead-Letter Queue** | `integration-layer/consumer.py` | Pesan gagal/malformed diarahkan ke `library.dlq` untuk audit |
| **Canonical Data Model** | `integration-layer/cdm/models.py` | Model perantara teknologi-agnostik (`LateFeeEventCDM`) |

---

## Dokumen Terkait

| Dokumen | Isi |
|---------|-----|
| [proposal.md](proposal.md) | Proposal tema, daftar aplikasi & format data, diagram arsitektur integrasi |
| [spesifikasi.md](spesifikasi.md) | Spesifikasi teknis lengkap semua komponen (stack, endpoint, skema DB) |
| [laporan.md](laporan.md) | Laporan EIP yang diterapkan, mapping transformasi data, kendala & solusi |
