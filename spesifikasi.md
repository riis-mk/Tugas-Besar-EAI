# Spesifikasi Komponen — Integrasi Aplikasi Enterprise

Dokumen ini merinci spesifikasi teknis seluruh komponen dalam sistem integrasi SIAKAD × Keuangan × Perpustakaan.

---

## Daftar Isi

1. [Infrastruktur & Runtime](#1-infrastruktur--runtime)
2. [Message Broker — RabbitMQ](#2-message-broker--rabbitmq)
3. [Microservice 1 — Perpustakaan](#3-microservice-1--perpustakaan)
4. [Microservice 2 — Keuangan](#4-microservice-2--keuangan)
5. [Microservice 3 — SIAKAD](#5-microservice-3--siakad)
6. [Integration Layer](#6-integration-layer)
7. [Skema Database](#7-skema-database)
8. [Protokol Komunikasi Antar Layanan](#8-protokol-komunikasi-antar-layanan)
9. [Enterprise Integration Patterns (EIP)](#9-enterprise-integration-patterns-eip)

---

## 1. Infrastruktur & Runtime

| Komponen | Teknologi | Versi |
|---|---|---|
| Containerization | Docker + Docker Compose | Compose v2 |
| Base Image semua service | Python | 3.11-slim |
| Sistem Operasi Container | Debian Slim (Linux) | — |

Seluruh service didefinisikan dalam satu file `docker-compose.yml` dan berkomunikasi melalui Docker internal network. Tidak ada service yang mengekspos port database ke host.

---

## 2. Message Broker — RabbitMQ

| Aspek | Detail |
|---|---|
| **Image** | `rabbitmq:3.13-management` |
| **Port AMQP** | 5672 |
| **Port Management UI** | 15672 → `http://localhost:15672` |
| **Exchange** | `library.exchange` (type: **topic**, durable) |
| **Queue Utama** | `library.events.queue` (durable) |
| **Binding Key** | `book.return.#` |
| **Dead-Letter Exchange** | `library.dlx` (type: direct) |
| **Dead-Letter Queue** | `library.dlq` (durable) |
| **Persistensi Data** | Docker volume `rabbitmq_data` |

### Topologi Queue

```
library.exchange (topic)
    └── binding: book.return.#
            ▼
    library.events.queue
        │  x-dead-letter-exchange → library.dlx
        │
        └── (nack / reject permanen)
                    ▼
            library.dlx  ──► library.dlq
```

---

## 3. Microservice 1 — Perpustakaan

### Stack Teknologi

| Aspek | Detail | Versi |
|---|---|---|
| **Framework Web** | FastAPI | 0.111.0 |
| **Web Server** | Uvicorn (ASGI) | 0.29.0 |
| **Database** | PostgreSQL (Alpine) | 16 |
| **ORM** | SQLAlchemy | 2.0.30 |
| **Driver DB** | psycopg2-binary | 2.9.9 |
| **Validasi Data** | Pydantic | 2.7.1 |
| **RabbitMQ Client** | Pika | 1.3.2 |
| **Port (host)** | 8001 | — |
| **Protokol API** | REST / JSON | — |
| **Dokumentasi** | Swagger UI otomatis | `http://localhost:8001/docs` |

### Endpoints

| Method | Path | Deskripsi |
|---|---|---|
| `POST` | `/books/` | Tambah buku baru |
| `GET` | `/books/` | Daftar semua buku |
| `GET` | `/books/{book_id}` | Detail buku |
| `POST` | `/loans/` | Buat transaksi peminjaman |
| `PATCH` | `/loans/{loan_id}/return` | Kembalikan buku — **memicu event RabbitMQ jika terlambat** |

### Behaviour Integrasi

Ketika `return_date > due_date`, service mempublikasikan event `book.return.late` ke RabbitMQ dengan payload JSON yang berisi data mahasiswa, buku, dan detail keterlambatan termasuk kalkulasi denda (Rp 5.000/hari).

---

## 4. Microservice 2 — Keuangan

### Stack Teknologi

| Aspek | Detail | Versi |
|---|---|---|
| **Framework Web** | Flask | 3.0.3 |
| **Web Server** | Waitress (WSGI, production) | 3.0.0 |
| **Database** | MySQL | 8.0 |
| **ORM** | SQLAlchemy | 2.0.30 |
| **Driver DB** | PyMySQL | 1.1.1 |
| **SOAP Library** | Spyne | 2.14.0 |
| **XML Parser** | lxml | 5.2.1 |
| **Port (host)** | 8002 | — |
| **Protokol API** | SOAP 1.1 / XML | — |
| **WSDL** | `http://localhost:8002/soap?wsdl` | — |

### Endpoints

| Method | Path | Deskripsi |
|---|---|---|
| `POST` | `/soap` | Endpoint SOAP 1.1 — operasi `CreateFine` |
| `GET` | `/soap?wsdl` | WSDL descriptor layanan |

### Operasi SOAP

**`CreateFine`** — Membuat record tagihan denda keterlambatan.

| Parameter SOAP | Tipe | Keterangan |
|---|---|---|
| `studentNim` | Unicode | NIM mahasiswa |
| `studentName` | Unicode | Nama mahasiswa |
| `loanId` | Unicode | ID peminjaman (referensi) |
| `bookTitle` | Unicode | Judul buku |
| `totalFee` | Unicode | Total denda (dalam string numerik) |
| `overdueDays` | Integer | Jumlah hari keterlambatan |
| `currency` | Unicode | Mata uang (default: IDR) |
| **Return** | Unicode | `fine_id` — UUID record denda yang dibuat |

> Namespace TNS: `http://keuangan.eai.university/soap`

---

## 5. Microservice 3 — SIAKAD

### Stack Teknologi

| Aspek | Detail | Versi |
|---|---|---|
| **Framework Web** | FastAPI | 0.111.0 |
| **Web Server** | Uvicorn (ASGI) | 0.29.0 |
| **Database** | PostgreSQL (Alpine) | 16 |
| **ORM** | SQLAlchemy | 2.0.30 |
| **Driver DB** | psycopg2-binary | 2.9.9 |
| **Validasi Data** | Pydantic | 2.7.1 |
| **Port (host)** | 8003 | — |
| **Protokol API** | REST / JSON | — |
| **Dokumentasi** | Swagger UI otomatis | `http://localhost:8003/docs` |

### Endpoints

| Method | Path | Deskripsi |
|---|---|---|
| `POST` | `/students/` | Tambah data mahasiswa |
| `GET` | `/students/{nim}` | Detail mahasiswa berdasarkan NIM |
| `PATCH` | `/students/{nim}/status` | Perbarui status akademik |

### Status Akademik

| Nilai | Keterangan |
|---|---|
| `ACTIVE` | Mahasiswa aktif (default) |
| `SUSPENDED` | Ditangguhkan — dipicu oleh Integration Layer |
| `GRADUATED` | Lulus |

---

## 6. Integration Layer

### Stack Teknologi

| Aspek | Detail | Versi |
|---|---|---|
| **Runtime** | Pure Python (tanpa framework web) | 3.11 |
| **RabbitMQ Client** | Pika | 1.3.2 |
| **HTTP Client** | Requests | 2.31.0 |
| **XML Builder** | lxml | 5.2.1 |
| **Retry Library** | Tenacity | 8.3.0 |
| **Validasi CDM** | Pydantic | 2.7.1 |
| **Port** | Tidak ada (consumer only) | — |

### Struktur Internal

```
integration-layer/app/
├── consumer.py          ← Entry point: RabbitMQ listener
├── router.py            ← Content-Based Router
├── cdm/
│   └── models.py        ← Canonical Data Model (CDM)
├── translators/
│   ├── json_to_cdm.py   ← Message Translator: JSON → CDM
│   └── cdm_to_soap.py   ← Message Translator: CDM → SOAP XML
└── clients/
    ├── keuangan_client.py  ← HTTP client untuk service Keuangan
    └── siakad_client.py    ← HTTP client untuk service SIAKAD
```

### Canonical Data Model (CDM)

Model perantara teknologi-agnostik yang memisahkan format sumber dari format tujuan.

| Model | Field |
|---|---|
| `LateFeeEventCDM` | event_id, event_type, timestamp, student, book, loan |
| `StudentCDM` | id, nim, name |
| `BookCDM` | id, title, isbn |
| `LoanCDM` | id, due_date, return_date, overdue_days, fee_per_day, total_fee, currency |

### Alur Pemrosesan Message

```
[RabbitMQ] → consumer.py
                │
                ├── [1] json_to_cdm.py    JSON bytes → LateFeeEventCDM
                │
                ├── [2] router.py         dispatch berdasarkan event_type
                │
                ├── [3] cdm_to_soap.py    LateFeeEventCDM → SOAP 1.1 XML
                │         └── keuangan_client.py  POST /soap  → fine_id
                │
                └── [4] siakad_client.py  PATCH /students/{nim}/status
                          (hanya jika step 3 sukses)
```

### Strategi Error Handling

| Kondisi | Aksi |
|---|---|
| Payload JSON malformed | `basic_reject` → DLQ (tidak di-retry) |
| Error transient (service down, timeout) | `basic_nack` + requeue sekali |
| Error setelah retry | `basic_reject` → DLQ (audit) |
| Sukses | `basic_ack` |

---

## 7. Skema Database

### PostgreSQL — Perpustakaan

**Tabel `books`**

| Kolom | Tipe | Constraint |
|---|---|---|
| id | String (UUID) | PRIMARY KEY |
| title | String(500) | NOT NULL |
| isbn | String(20) | UNIQUE |
| author | String(200) | — |

**Tabel `students`**

| Kolom | Tipe | Constraint |
|---|---|---|
| id | String (UUID) | PRIMARY KEY |
| nim | String(20) | UNIQUE, NOT NULL |
| name | String(200) | NOT NULL |

**Tabel `loans`**

| Kolom | Tipe | Constraint |
|---|---|---|
| id | String (UUID) | PRIMARY KEY |
| book_id | String | FK → books.id, NOT NULL |
| student_id | String | FK → students.id, NOT NULL |
| loan_date | Date | NOT NULL |
| due_date | Date | NOT NULL |
| return_date | Date | NULL (kosong jika belum dikembalikan) |

---

### MySQL — Keuangan

**Tabel `fines`**

| Kolom | Tipe | Constraint |
|---|---|---|
| id | String(36) UUID | PRIMARY KEY |
| student_nim | String(50) | NOT NULL |
| student_name | String(200) | NOT NULL |
| loan_id | String(36) | NOT NULL, UNIQUE |
| book_title | String(500) | NOT NULL |
| overdue_days | Integer | NOT NULL |
| total_fee | Numeric(15,2) | NOT NULL |
| currency | String(3) | default: IDR |
| status | String(20) | default: ACTIVE |
| created_at | DateTime | default: now() |

---

### PostgreSQL — SIAKAD

**Tabel `students`**

| Kolom | Tipe | Constraint |
|---|---|---|
| id | String (UUID) | PRIMARY KEY |
| nim | String(20) | UNIQUE, NOT NULL |
| name | String(200) | NOT NULL |
| academic_status | String(20) | default: ACTIVE |
| program_studi | String(100) | — |
| angkatan | String(4) | — |

---

## 8. Protokol Komunikasi Antar Layanan

| Arah | Protokol | Format | Detail |
|---|---|---|---|
| Perpustakaan → RabbitMQ | AMQP | JSON | routing key: `book.return.late` |
| RabbitMQ → Integration Layer | AMQP | JSON | queue: `library.events.queue` |
| Integration Layer → Keuangan | HTTP | SOAP 1.1 XML | `POST http://keuangan:8000/soap` |
| Integration Layer → SIAKAD | HTTP | REST JSON | `PATCH http://siakad:8000/students/{nim}/status` |

### Format JSON Event (Perpustakaan → RabbitMQ)

```json
{
  "event_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "event_type": "book.return.late",
  "timestamp": "2025-06-02T08:30:00+00:00",
  "student": { "id": "...", "nim": "102022400067", "name": "Paris" },
  "book":    { "id": "...", "title": "Pengantar EAI", "isbn": "978-..." },
  "loan": {
    "id": "...",
    "due_date": "2025-05-15T00:00:00",
    "return_date": "2025-06-02T00:00:00",
    "overdue_days": 18,
    "fee_per_day": "5000.0",
    "total_fee": "90000.0",
    "currency": "IDR"
  }
}
```

### Format SOAP Envelope (Integration Layer → Keuangan)

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
      <loanId>c3d4e5f6-...</loanId>
      <bookTitle>Pengantar EAI</bookTitle>
      <totalFee>90000.0</totalFee>
      <overdueDays>18</overdueDays>
      <currency>IDR</currency>
    </tns:CreateFine>
  </soapenv:Body>
</soapenv:Envelope>
```

### Format REST JSON (Integration Layer → SIAKAD)

```json
PATCH /students/102022400067/status

{
  "status": "SUSPENDED",
  "reason": "Keterlambatan pengembalian buku \"Pengantar EAI\" selama 18 hari. Denda: IDR 90000.0. Referensi tagihan: <fine_id>."
}
```

---

## 9. Enterprise Integration Patterns (EIP)

| Pattern | Lokasi Implementasi | Deskripsi |
|---|---|---|
| **Publish-Subscribe** | `perpustakaan/app/publisher.py` + `integration-layer/app/consumer.py` | Topic exchange memungkinkan banyak subscriber tanpa perubahan pada publisher |
| **Message Translator** | `integration-layer/app/translators/json_to_cdm.py` | Mengkonversi JSON raw bytes dari Perpustakaan ke CDM teknologi-agnostik |
| **Message Translator** | `integration-layer/app/translators/cdm_to_soap.py` | Mengkonversi CDM ke SOAP 1.1 XML envelope untuk Keuangan |
| **Canonical Data Model** | `integration-layer/app/cdm/models.py` | Model perantara (`LateFeeEventCDM`) yang memisahkan format sumber dan tujuan |
| **Content-Based Router** | `integration-layer/app/router.py` | Routing berdasarkan nilai `event_type` dalam CDM |
| **Dead-Letter Queue** | `integration-layer/app/consumer.py` | Pesan gagal/malformed diarahkan ke `library.dlq` untuk audit tanpa kehilangan data |

---

## Ringkasan Port & Akses

| Service | URL | Keterangan |
|---|---|---|
| Perpustakaan API | `http://localhost:8001` | REST — Swagger UI: `/docs` |
| Keuangan SOAP | `http://localhost:8002/soap` | SOAP 1.1 — WSDL: `/soap?wsdl` |
| SIAKAD API | `http://localhost:8003` | REST — Swagger UI: `/docs` |
| RabbitMQ Management | `http://localhost:15672` | UI monitoring antrian |
