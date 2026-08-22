<div align="center">

# AI Log Detective

### Production Incident Investigation Target for AegisAI

**A deliberately structured payment service built to turn production-style failures into traceable engineering evidence.**

<br>

<img src="https://img.shields.io/badge/Python-010D19?style=for-the-badge&logo=python&logoColor=EDBE91" alt="Python">
<img src="https://img.shields.io/badge/FastAPI-010D19?style=for-the-badge&logo=fastapi&logoColor=D99B91" alt="FastAPI">
<img src="https://img.shields.io/badge/Production%20Reliability-010D19?style=for-the-badge&logoColor=B48195" alt="Production Reliability">
<img src="https://img.shields.io/badge/AI%20Investigation-010D19?style=for-the-badge&logoColor=856E8D" alt="AI Investigation">

<br><br>

<table>
<tr>
<td align="center" width="25%"><b>01</b><br><sub>INCIDENT</sub></td>
<td align="center" width="25%"><b>02</b><br><sub>EVIDENCE</sub></td>
<td align="center" width="25%"><b>03</b><br><sub>LOCALIZATION</sub></td>
<td align="center" width="25%"><b>04</b><br><sub>REMEDIATION</sub></td>
</tr>
</table>

</div>

---

## 01 — What This Repository Is

**AI Log Detective is not the AI engine itself.** It is the **production-like application under investigation** by the AegisAI Reliability Engine.

The repository contains a small FastAPI payment service with a deliberately defined database dependency and failure path. This gives AegisAI a realistic target against which it can perform:

```text
Production-style failure
        │
        ▼
     Log event
        │
        ▼
   Incident context
        │
        ▼
  Evidence correlation
        │
        ▼
    Root-cause analysis
        │
        ▼
    Code localization
        │
        ▼
 services/payment-api/app/database.py
        │
        ▼
     Repair candidate
```

The important distinction is architectural: **this repository provides the failure surface; AegisAI provides the investigation and controlled remediation workflow.**

---

## 02 — The Engineering Problem

In a real production incident, an error message is only the beginning.

An engineer needs to answer:

| Question | Investigation target |
|---|---|
| What failed? | Payment request / database dependency |
| Where did it fail? | `services/payment-api/app/database.py` |
| Which dependency is involved? | `payments-primary` |
| What is the failure mode? | Database connection timeout |
| Where should an investigator look? | `get_database_connection()` |
| What should the system eventually produce? | Evidence-backed code localization and repair candidate |

This repository exists to make those questions concrete rather than theoretical.

---

## 03 — Failure Surface

The payment service defines a primary database dependency:

```text
DATABASE_HOST   = payments-primary
DATABASE_REGION = ap-south-1
```

The connection boundary is implemented in:

```text
services/payment-api/app/database.py
```

The connection routine performs a bounded three-attempt sequence and ultimately preserves the underlying `TimeoutError` when the dependency remains unavailable.

```text
get_database_connection()
        │
        ├── attempt 1
        ├── attempt 2
        └── attempt 3
              │
              ▼
       TimeoutError preserved
```

This bounded behavior is intentional: it creates a concrete execution path that can be inspected by the reliability workflow.

---

## 04 — Request Path

The payment API exposes a `/payments` router and a health endpoint.

```text
POST /payments
       │
       ▼
process_payment()
       │
       ▼
get_database_connection()
       │
       ▼
payments-primary
       │
       ├── connection succeeds → payment continues
       │
       └── timeout → logged failure → HTTP 503
```

The application also exposes:

```text
GET /health
```

with a healthy `payment-api` service response.

---

## 05 — Why This Is Useful for AegisAI

AegisAI is designed around the following reliability pipeline:

```text
┌──────────────────────────────────────────────────────────────┐
│                    PRODUCTION INCIDENT                       │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                         LOG EVIDENCE                          │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                         DETECTION                             │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                        CORRELATION                            │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    ROOT-CAUSE ANALYSIS                        │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                       CODE LOCALIZATION                       │
│        services/payment-api/app/database.py                   │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                     REPAIR CANDIDATE                          │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                 VALIDATION + SAFETY CHECKS                    │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
                         GITHUB PULL REQUEST
```

This makes the repository a **controlled investigation target** rather than a toy error generator.

---

## 06 — Repository Structure

```text
ai-log-detective/
│
├── services/
│   └── payment-api/
│       ├── app/
│       │   ├── __init__.py
│       │   ├── database.py       # Database dependency + failure boundary
│       │   ├── main.py           # FastAPI application entry point
│       │   └── payments.py       # Payment request flow + error handling
│       │
│       └── requirements.txt
│
├── .gitignore
└── README.md
```

### Key source boundaries

| File | Responsibility |
|---|---|
| `main.py` | Creates the FastAPI application and `/health` endpoint |
| `payments.py` | Handles payment requests and converts database timeout failures into HTTP 503 responses |
| `database.py` | Defines the `payments-primary` dependency and bounded connection attempt behavior |

---

## 07 — Technology Surface

<div align="center">

| Layer | Technology |
|:---|:---|
| Runtime | Python |
| API framework | FastAPI |
| Service design | REST API |
| Logging | Python `logging` |
| Dependency boundary | Async database connection abstraction |
| Investigation consumer | AegisAI Reliability Engine |

</div>

---

## 08 — Investigation Target at a Glance

```text
SERVICE
└── payment-api

DEPENDENCY
└── payments-primary
    └── region: ap-south-1

FAILURE
└── Database connection timeout

SOURCE BOUNDARY
└── services/payment-api/app/database.py
    └── get_database_connection()

REQUEST HANDLER
└── services/payment-api/app/payments.py
    └── POST /payments

FAILURE RESPONSE
└── HTTP 503
    └── Payment service temporarily unavailable
```

---

## 09 — Design Principle

The repository intentionally keeps the failure **observable and bounded**.

A reliability system should be able to identify the failure without requiring the target application to hide it behind artificial abstraction.

The payment service therefore preserves the underlying timeout after its bounded retry path, while the request layer records the incident and returns a service-unavailable response.

That gives AegisAI a traceable chain:

```text
Exception
   ↓
Application log
   ↓
Incident evidence
   ↓
Service correlation
   ↓
Source localization
   ↓
Repair boundary
```

---

## 10 — How It Fits Into the Larger System

```text
                     AegisAI
          AI-Powered Reliability Engine
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
 Incident Investigation       Controlled Remediation
        │                             │
        └──────────────┬──────────────┘
                       │
                       ▼
              AI Log Detective
                       │
                       ▼
                payment-api
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
      payments.py              database.py
          │                         │
          └────────────┬────────────┘
                       ▼
                Failure Evidence
```

The target application remains separate from the remediation engine. This separation is important for testing investigation logic without allowing the investigation system to become the application it is supposed to inspect.

---

## 11 — Local Development

### Clone

```bash
git clone https://github.com/deekshitaa1/ai-log-detective.git
cd ai-log-detective
```

### Install dependencies

```bash
cd services/payment-api
pip install -r requirements.txt
```

### Run the API

```bash
uvicorn app.main:app --reload
```

The service exposes:

```text
GET  /health
POST /payments
```

FastAPI documentation is available through the standard development server documentation route.

---

## 12 — Example Investigation Scenario

A payment request reaches the service:

```text
POST /payments
```

The request attempts to obtain a database connection:

```text
get_database_connection()
```

The dependency is unavailable:

```text
payments-primary
```

The application records:

```text
Database connection timeout while processing payment request
```

The request returns:

```text
503 Service Unavailable
```

The investigation target is therefore localized around:

```text
services/payment-api/app/database.py
```

and specifically:

```text
get_database_connection()
```

This is the evidence chain that AegisAI is designed to consume.

---

## 13 — Professional Color System

The README uses a restrained engineering palette based on the supplied visual reference.

<table>
<tr>
<td width="20%" bgcolor="#010D19"><br><br></td>
<td width="20%" bgcolor="#EDBE91"><br><br></td>
<td width="20%" bgcolor="#D99B91"><br><br></td>
<td width="20%" bgcolor="#B48195"><br><br></td>
<td width="20%" bgcolor="#856E8D"><br><br></td>
</tr>
<tr>
<td align="center"><code>#010D19</code><br><sub>Core background</sub></td>
<td align="center"><code>#EDBE91</code><br><sub>Primary accent</sub></td>
<td align="center"><code>#D99B91</code><br><sub>Warm signal</sub></td>
<td align="center"><code>#B48195</code><br><sub>Secondary signal</sub></td>
<td align="center"><code>#856E8D</code><br><sub>Deep accent</sub></td>
</tr>
</table>

The palette is intentionally muted: **dark infrastructure foundation + warm diagnostic accents**, rather than a playful or overly colorful developer aesthetic.

---

## 14 — Engineering Intent

This repository is intentionally small because its purpose is not to demonstrate how many files can be written.

Its purpose is to provide a **clear, reproducible failure surface** that an AI reliability system can investigate.

The design emphasizes:

```text
Observable failure
        +
Traceable dependency
        +
Clear source boundary
        +
Bounded behavior
        +
Reviewable remediation
        ─────────────────────
        =
Reliable AI investigation target
```

---

## 15 — Related System

**AegisAI Reliability Engine** consumes this repository as an investigation target and is designed to move from production evidence toward a reviewable remediation workflow.

The larger system follows:

```text
Detect
  ↓
Correlate
  ↓
Analyze
  ↓
Localize
  ↓
Propose
  ↓
Validate
  ↓
Verify
  ↓
Create PR
  ↓
Human Review
```

The final engineering boundary is deliberately a pull request rather than an uncontrolled production modification.

---

## 16 — Repository

<div align="center">

**AI Log Detective**

Production-style payment service for AI-assisted reliability investigation.

[View Repository](https://github.com/deekshitaa1/ai-log-detective)

</div>

---

<div align="center">

### Evidence first. Localization second. Remediation under control.

<sub>Built as an investigation target for AegisAI Reliability Engineering.</sub>

</div>
