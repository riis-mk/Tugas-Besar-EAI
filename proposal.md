# Proposal Tugas Besar — Integrasi Aplikasi Enterprise

**Mata Kuliah :** Integrasi Aplikasi Enterprise  
**Semester :** 4  
**Anggota Kelompok :**

| NIM | Nama |
|-----|------|
| 102022400067 | Paris |
| 102022400067 | Jazman Jati Muhtadi |

---

## 1. Tema & Judul Proyek

**Judul :**  
> **SIAKAD × Keuangan × Perpustakaan — Integrasi Event-Driven Berbasis RabbitMQ**

**Tema :** Integrasi sistem informasi kampus yang heterogen menggunakan arsitektur *message-driven* (Event-Driven Architecture / EDA) dengan RabbitMQ sebagai message broker dan sebuah Integration Layer sebagai mediator tunggal.

---

## 2. Latar Belakang

Sistem informasi di lingkungan perguruan tinggi umumnya berkembang secara organik — masing-masing unit (akademik, keuangan, perpustakaan) membangun aplikasinya sendiri dengan tumpukan teknologi yang berbeda-beda. Akibatnya, perubahan data di satu sistem tidak otomatis tercermin di sistem lain.

Contoh nyata: ketika seorang mahasiswa terlambat mengembalikan buku, Perpustakaan mencatat pelanggaran tersebut, tetapi Keuangan tidak langsung mengetahui denda yang harus ditagih dan SIAKAD tidak langsung mengetahui bahwa status akademik mahasiswa perlu ditangguhkan.

Proyek ini memodelkan dan mengimplementasikan solusi integrasi nyata untuk skenario tersebut, dengan memperhatikan heterogenitas protokol (AMQP, SOAP, REST) dan format data (JSON, XML) yang lazim ditemukan di lingkungan enterprise.

---

## 3. Tujuan

1. Mengintegrasikan tiga sistem mandiri (Perpustakaan, Keuangan, SIAKAD) tanpa mengubah logika internal masing-masing sistem.
2. Menerapkan minimal empat *Enterprise Integration Patterns* (EIP) dari katalog Hohpe & Woolf.
3. Menangani heterogenitas protokol dan format data melalui Integration Layer yang terpusat.
4. Membangun observabilitas dasar dengan Dead-Letter Queue untuk pesan gagal.
5. Mendokumentasikan seluruh alur integrasi agar dapat direproduksi dari nol hanya dengan `docker compose up --build`.

---

## 4. Daftar Aplikasi & Format Data

### 4.1 Ringkasan Sistem

| # | Sistem | Peran | Framework | Database | Protokol API | Port |
|---|--------|-------|-----------|----------|-------------|------|
| 1 | **Perpustakaan** | *Event Source* — mempublikasikan event keterlambatan | FastAPI (Python) | PostgreSQL 16 | REST/JSON + AMQP publish | 8001 |
| 2 | **Keuangan** | *Event Consumer* via Integration Layer — mencatat denda | Flask + Spyne (Python) | MySQL 8.0 | SOAP 1.1 / XML | 8002 |
| 3 | **SIAKAD** | *Event Consumer* via Integration Layer — update status akademik | FastAPI (Python) | PostgreSQL 16 | REST / JSON | 8003 |
| 4 | **Integration Layer** | *Mediator* — consumer RabbitMQ, routing, translation | Pure Python | — (stateless) | AMQP consumer / HTTP client | — |
| 5 | **RabbitMQ** | *Message Broker* | RabbitMQ 3.13 + Management | — | AMQP 0-9-1 | 5672 / 15672 |

---

### 4.2 Format Data Per Sistem

#### Sistem 1 — Perpustakaan (FastAPI + PostgreSQL)

**Endpoint yang relevan untuk integrasi:**

| Method | Path | Format Request | Format Response |
|--------|------|---------------|----------------|
| `PATCH` | `/loans/{loan_id}/return` | JSON | JSON |

**Payload request pengembalian buku:**
```json
{
  "return_date": "2025-06-04"
}
```

**Event yang dipublikasikan ke RabbitMQ** (routing key: `book.return.late`):
```json
{
  "event_id":   "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "event_type": "book.return.late",
  "timestamp":  "2025-06-04T08:30:00+00:00",
  "student": {
    "id":   "a1b2c3d4-...",
    "nim":  "102022400067",
    "name": "Paris"
  },
  "book": {
    "id":    "e5f6g7h8-...",
    "title": "Pengantar EAI",
    "isbn":  "978-602-123-456"
  },
  "loan": {
    "id":           "c3d4e5f6-...",
    "due_date":     "2025-05-15T00:00:00",
    "return_date":  "2025-06-04T00:00:00",
    "overdue_days": 20,
    "fee_per_day":  "5000.0",
    "total_fee":    "100000.0",
    "currency":     "IDR"
  }
}
```

**Skema database (PostgreSQL):**

| Tabel | Kolom Utama |
|-------|------------|
| `books` | `id` (UUID PK), `title`, `isbn` (UNIQUE), `author` |
| `students` | `id` (UUID PK), `nim` (UNIQUE), `name` |
| `loans` | `id` (UUID PK), `book_id` (FK), `student_id` (FK), `loan_date`, `due_date`, `return_date` (nullable) |

---

#### Sistem 2 — Keuangan (Flask + Spyne + MySQL)

**Endpoint SOAP:**

| Method | Path | Format |
|--------|------|--------|
| `POST` | `/soap` | SOAP 1.1 XML |
| `GET` | `/soap?wsdl` | WSDL XML |

**SOAP Envelope yang diterima** (dikirim oleh Integration Layer):
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
      <totalFee>100000.0</totalFee>
      <overdueDays>20</overdueDays>
      <currency>IDR</currency>
    </tns:CreateFine>
  </soapenv:Body>
</soapenv:Envelope>
```

**SOAP Response:**
```xml
<soapenv:Envelope ...>
  <soapenv:Body>
    <tns:CreateFineResponse>
      <CreateFineResult>d9e0f1a2-...</CreateFineResult>
    </tns:CreateFineResponse>
  </soapenv:Body>
</soapenv:Envelope>
```

**Skema database (MySQL):**

| Tabel | Kolom Utama |
|-------|------------|
| `fines` | `id` (UUID PK), `student_nim`, `student_name`, `loan_id` (UNIQUE), `book_title`, `overdue_days`, `total_fee` (Numeric 15,2), `currency`, `status`, `created_at` |

---

#### Sistem 3 — SIAKAD (FastAPI + PostgreSQL)

**Endpoint yang menerima dari Integration Layer:**

| Method | Path | Format Request | Format Response |
|--------|------|---------------|----------------|
| `PATCH` | `/students/{nim}/status` | JSON | JSON |

**Payload request status update:**
```json
{
  "status": "SUSPENDED",
  "reason": "Keterlambatan pengembalian buku \"Pengantar EAI\" selama 20 hari. Denda: IDR 100000.0. Referensi tagihan: d9e0f1a2-..."
}
```

**Response:**
```json
{
  "nim":        "102022400067",
  "name":       "Paris",
  "old_status": "ACTIVE",
  "new_status": "SUSPENDED",
  "reason":     "Keterlambatan pengembalian buku ..."
}
```

**Skema database (PostgreSQL):**

| Tabel | Kolom Utama |
|-------|------------|
| `students` | `id` (UUID PK), `nim` (UNIQUE), `name`, `academic_status` (ACTIVE/SUSPENDED/GRADUATED), `program_studi`, `angkatan` |

---

#### Integration Layer — Canonical Data Model (CDM)

CDM adalah representasi data netral-teknologi yang menjadi jembatan antara JSON (Perpustakaan) dan SOAP XML (Keuangan):

```
LateFeeEventCDM
├── event_id    : UUID
├── event_type  : str          ("book.return.late")
├── timestamp   : datetime
├── student     : StudentCDM
│   ├── id      : UUID
│   ├── nim     : str
│   └── name    : str
├── book        : BookCDM
│   ├── id      : UUID
│   ├── title   : str
│   └── isbn    : str
└── loan        : LoanCDM
    ├── id           : UUID
    ├── due_date     : datetime
    ├── return_date  : datetime
    ├── overdue_days : int
    ├── fee_per_day  : Decimal
    ├── total_fee    : Decimal
    └── currency     : str
```

---

### 4.3 Pemetaan Format Lintas Sistem

| Field Logis | JSON (Perpustakaan → Broker) | CDM (Integration Layer) | SOAP XML (→ Keuangan) | REST JSON (→ SIAKAD) |
|-------------|------------------------------|------------------------|----------------------|---------------------|
| NIM mahasiswa | `student.nim` | `student.nim` | `<studentNim>` | path param `{nim}` |
| Nama mahasiswa | `student.name` | `student.name` | `<studentName>` | — |
| ID pinjaman | `loan.id` | `loan.id` | `<loanId>` | — (di reason) |
| Judul buku | `book.title` | `book.title` | `<bookTitle>` | — (di reason) |
| Total denda | `loan.total_fee` (str) | `loan.total_fee` (Decimal) | `<totalFee>` (str) | — (di reason) |
| Hari telat | `loan.overdue_days` (int) | `loan.overdue_days` (int) | `<overdueDays>` (int) | — (di reason) |
| Status baru | — | — | — | `status: "SUSPENDED"` |

---

## 5. Diagram Arsitektur Integrasi

### 5.1 Topologi Tingkat Tinggi

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Docker Network (bridge)                       │
│                                                                        │
│  ┌─────────────────┐    AMQP/JSON     ┌──────────────────────────┐   │
│  │  Perpustakaan   │ ───────────────► │       RabbitMQ           │   │
│  │  FastAPI :8001  │  routing key:    │  library.exchange        │   │
│  │  PostgreSQL     │  book.return.late│  (topic exchange)        │   │
│  └─────────────────┘                 │                          │   │
│                                      │  library.events.queue ──►│   │
│                                      │  library.dlq (DLQ)       │   │
│                                      └─────────┬────────────────┘   │
│                                                │ AMQP consume        │
│                                                ▼                     │
│                                   ┌────────────────────────┐        │
│                                   │   Integration Layer     │        │
│                                   │   (EAI Hub)             │        │
│                                   │                         │        │
│                                   │  consumer.py            │        │
│                                   │     ▼                   │        │
│                                   │  json_to_cdm.py         │        │
│                                   │  [Message Translator ①] │        │
│                                   │     ▼                   │        │
│                                   │  router.py              │        │
│                                   │  [Content-Based Router] │        │
│                                   │     ▼                   │        │
│                                   │  cdm_to_soap.py         │        │
│                                   │  [Message Translator ②] │        │
│                                   └───────┬─────────────────┘        │
│                                           │                           │
│                    ┌──────────────────────┴──────────────────────┐   │
│                    │ SOAP 1.1 / XML                REST / JSON   │   │
│                    ▼                                             ▼   │
│  ┌─────────────────────────┐              ┌─────────────────────┐   │
│  │    Keuangan             │              │       SIAKAD        │   │
│  │    Flask+Spyne :8002    │              │    FastAPI :8003     │   │
│  │    MySQL                │              │    PostgreSQL        │   │
│  │  POST /soap             │              │  PATCH /students/    │   │
│  │  → CreateFine()         │              │      {nim}/status    │   │
│  │  ← fine_id (UUID)       │              │  → SUSPENDED         │   │
│  └─────────────────────────┘              └─────────────────────┘   │
│                                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.2 Alur Data End-to-End (Sequence)

```
Mahasiswa          Perpustakaan       RabbitMQ          Integration Layer      Keuangan          SIAKAD
    │                   │                │                       │                  │                │
    │ PATCH /loans/     │                │                       │                  │                │
    │ {id}/return       │                │                       │                  │                │
    │──────────────────►│                │                       │                  │                │
    │                   │ publish JSON   │                       │                  │                │
    │                   │ book.return.late                       │                  │                │
    │                   │───────────────►│                       │                  │                │
    │  200 OK           │                │                       │                  │                │
    │◄──────────────────│                │ deliver message       │                  │                │
    │                   │                │──────────────────────►│                  │                │
    │                   │                │                       │ json_to_cdm      │                │
    │                   │                │                       │─────────────┐    │                │
    │                   │                │                       │◄────────────┘    │                │
    │                   │                │                       │ cdm_to_soap      │                │
    │                   │                │                       │─────────────┐    │                │
    │                   │                │                       │◄────────────┘    │                │
    │                   │                │                       │ POST /soap       │                │
    │                   │                │                       │─────────────────►│                │
    │                   │                │                       │  fine_id         │                │
    │                   │                │                       │◄─────────────────│                │
    │                   │                │                       │ PATCH /students/ │                │
    │                   │                │                       │ {nim}/status     │                │
    │                   │                │                       │──────────────────────────────────►│
    │                   │                │                       │                  │  SUSPENDED     │
    │                   │                │                       │◄──────────────────────────────────│
    │                   │                │                       │ basic_ack        │                │
    │                   │                │◄──────────────────────│                  │                │
```

### 5.3 EIP yang Diterapkan

```
┌─────────────────────────────────────────────────────────┐
│              Enterprise Integration Patterns             │
├──────────────────────┬──────────────────────────────────┤
│ Pattern              │ Lokasi                            │
├──────────────────────┼──────────────────────────────────┤
│ Publish-Subscribe    │ publisher.py ↔ consumer.py        │
│ Message Translator①  │ translators/json_to_cdm.py        │
│ Canonical Data Model │ cdm/models.py                     │
│ Message Translator②  │ translators/cdm_to_soap.py        │
│ Content-Based Router │ router.py                         │
│ Dead-Letter Queue    │ consumer.py (x-dead-letter-exch.) │
└──────────────────────┴──────────────────────────────────┘
```

---

## 6. Rencana Implementasi

| Fase | Cakupan | Target |
|------|---------|--------|
| 1 | Setup Docker Compose + RabbitMQ + database | Minggu 1 |
| 2 | Implementasi Perpustakaan (FastAPI + publisher) | Minggu 2 |
| 3 | Implementasi Keuangan (Flask + Spyne SOAP) | Minggu 2 |
| 4 | Implementasi SIAKAD (FastAPI) | Minggu 3 |
| 5 | Integration Layer: consumer + CDM + translators + router | Minggu 3–4 |
| 6 | End-to-end test + Dead-Letter Queue | Minggu 4 |
| 7 | Dokumentasi + video demo | Minggu 5 |

---

## 7. Teknologi yang Digunakan

| Kategori | Teknologi | Versi |
|----------|-----------|-------|
| Containerization | Docker + Docker Compose v2 | latest |
| Message Broker | RabbitMQ | 3.13-management |
| Python Runtime | Python | 3.11-slim |
| REST Framework | FastAPI + Uvicorn | 0.111.0 / 0.29.0 |
| SOAP Framework | Flask + Spyne + Waitress | 3.0.3 / 2.14.0 / 3.0.0 |
| Database (RDBMS) | PostgreSQL | 16-alpine |
| Database (RDBMS) | MySQL | 8.0 |
| ORM | SQLAlchemy | 2.0.30 |
| Message Client | Pika (AMQP) | 1.3.2 |
| HTTP Client | Requests | 2.31.0 |
| XML Builder | lxml | 5.2.1 |
| Data Validation | Pydantic | 2.7.1 |
| Retry Logic | Tenacity | 8.3.0 |
