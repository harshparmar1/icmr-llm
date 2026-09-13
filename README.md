# ICMR-Guided Clinical Workflow Intelligence System (ICMR-STW AI)

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://python.org)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Store-orange.svg?style=flat)](https://trychroma.com)
[![Mistral AI](https://img.shields.io/badge/LLM-Mistral_AI-black.svg?style=flat)](https://mistral.ai)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL_/_Supabase-336791.svg?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat)](LICENSE)

An evidence-grounded **Clinical Decision-Support and Standard Treatment Workflow (STW) Intelligence Platform** powered by official guidelines published by the **Indian Council of Medical Research (ICMR)**.

The system ingests authoritative ICMR STW documents, extracts discrete clinical stages, embeds them into local high-performance vector collections, and provides an empathetic, conversational triage interface alongside evidence-grounded REST APIs.

> **Official ICMR STW Repository**: [https://www.icmr.gov.in/standard-treatment-workflows-stws](https://www.icmr.gov.in/standard-treatment-workflows-stws)

---

> [!IMPORTANT]
> **Clinical Safety & Legal Mandate**:  
> This platform is engineered strictly for **clinical decision-support, research, medical training, and educational purposes**. It does **NOT** provide autonomous medical prescriptions or replace qualified healthcare practitioners. Every recommendation is grounded in and cited to official ICMR Standard Treatment Workflow page numbers.

---

## 1. System Architecture

```
                                  +---------------------------------------+
                                  |  Official ICMR STW Guidelines (PDFs)  |
                                  +---------------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |   PDF Ingestion & Medical OCR Parser  |
                                  |         (PyMuPDF / pdfplumber)        |
                                  +---------------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  | Structured Chunking & Section Tagging |
                                  | (ICD-10, Specialty, Disease, Context) |
                                  +---------------------------------------+
                                                      |
                                 +--------------------+--------------------+
                                 |                                         |
                                 v                                         v
               +----------------------------------+       +----------------------------------+
               |      Relational Database         |       |      ChromaDB Vector Store       |
               | (Supabase PostgreSQL / SQLite)   |       |  (Dense Embeddings: all-MiniLM)  |
               +----------------------------------+       +----------------------------------+
                                 |                                         |
                                 +--------------------+--------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |   Hybrid Clinical Retrieval Engine    |
                                  | (Dense Semantic Search + BM25 Lexical)|
                                  +---------------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |   Strict Medical Domain Guardrails    |
                                  | (Greeting Fast-Path & Off-Topic Guard)|
                                  +---------------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |  LLM Provider (Mistral AI / OpenAI)   |
                                  |    (Structured JSON Triage & STW)     |
                                  +---------------------------------------+
                                                      |
                                 +--------------------+--------------------+
                                 |                                         |
                                 v                                         v
               +----------------------------------+       +----------------------------------+
               |       FastAPI REST Endpoints     |       |    Interactive Web Dashboard     |
               |      (/api/chat, /api/query)     |       |  (Urgency Triage, Stages, Cit.)  |
               +----------------------------------+       +----------------------------------+
```

---

## 2. Key Features

- **Evidence-Grounded RAG Pipeline**:
  - Combines **Dense Vector Search** (`SentenceTransformers all-MiniLM-L6-v2`) with **Lexical Keyword Retrieval** (`BM25`) for high precision on drug names, ICD-10 codes, and clinical symptoms.
  - Generates strict page-level citations for every clinical step.
- **Strict Medical Scope Guardrails**:
  - **Conversational Greetings**: Natural, friendly responses to openers (`hi`, `hello`, `good morning`, `how are you`, `who are you`) without generating irrelevant clinical error notices.
  - **Non-Medical Query Refusal**: Immediate detection and refusal for non-medical topics (coding, sports, history, politics, recipes, entertainment, etc.), ensuring the assistant stays strictly within its medical domain.
- **Clinical Urgency Triage**:
  - Automatically assesses inquiries into urgency tiers: `EMERGENCY`, `URGENT`, or `ROUTINE`.
  - Surfaces critical **Red Flag Alerts** that necessitate emergency tertiary care referral.
- **Discrete Workflow Decomposition**:
  - Breaks treatment protocols into standardized stages:
    1. *Initial Assessment*
    2. *Diagnostic Investigations*
    3. *Definitive Diagnosis*
    4. *Clinical Management (Pharmacological & Non-Pharmacological)*
    5. *Follow-up & Monitoring*
    6. *Referral Criteria*
- **Ultra-Low Latency Performance**:
  - Local vector store (`vector_db/chroma.sqlite3`) delivers **~17 ms** similarity searches.
  - Pre-warmed embedding model during server startup eliminates first-query cold starts.
  - Non-medical and greeting queries return in **< 50 ms**.
- **Interactive Web Dashboard**:
  - Built-in responsive clinical interface with 3D urgency badges, step-by-step workflow accordions, source citations, and collapsible technical logs.
- **Multi-Provider LLM Flexibility**:
  - Built-in provider abstractions for **Mistral AI** (`ministral-8b-latest`, `mistral-small-latest`), **OpenAI** (`gpt-4o-mini`, `gpt-4o`), **Groq**, and **Local SLMs** (via Ollama / vLLM).

---

## 3. Supported ICMR STW Specialties & Guidelines

The current ingestion dataset covers authoritative ICMR guidelines across multiple specialties:

| Specialty | Disease / Condition | ICD-10 Code | ICMR Document |
|---|---|---|---|
| **Cardiology** | Hypertension in Adults | I10 | `1778941063_hypertensioninadults_final.pdf` |
| **Cardiology** | Acute Coronary Syndrome | I20 - I25 | `1768823343_cardiology_1-1.pdf` |
| **Nephrology** | Acute Kidney Injury (AKI) | N17 | `1784807239_acutekidneyinjury-updated.pdf` |
| **Pulmonology** | Acute Respiratory Infections | J00 - J22 | `1725963734_pulmonology_acute_respiratory_infections.pdf` |
| **ENT** | Acute Rhinosinusitis | J01.90 | `1725952292_ent_acute_rhinosinusitis.pdf` |
| **Psychiatry** | Alcohol Use Disorders | F10 | `1725952335_psychiatry_alcohol_use_disorders.pdf` |
| **Neurology** | Acute Paralysis | G81 - G83 | `1725952346_neurology_acute_paralysis.pdf` |
| **Paediatrics** | Acute Encephalitis Syndrome (AES) | A85 - A86 | `1725959608_paediatrics_acute_encephalitis_syndrome.pdf` |
| **Obstetrics** | Antenatal Care (Normal Pregnancy) | Z34 | `1771568619_ante-natalmanagementofnormalpregnancy-7.pdf` |

---

## 4. Project Structure

```
medical-llm/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── endpoints/
│   │   │   │   ├── chat.py           # Conversational symptom triage & guardrails
│   │   │   │   ├── query.py          # Structured clinical workflow generation
│   │   │   │   └── stws.py           # STW document & catalog queries
│   │   │   └── router.py             # Main API router & health check
│   │   ├── core/
│   │   │   ├── config.py             # Settings & environment variables
│   │   │   └── security.py           # PHI redaction & sanitization
│   │   ├── database/
│   │   │   └── session.py            # SQLAlchemy engine & session manager
│   │   ├── models/                   # ORM models (Disease, Specialty, Audit logs)
│   │   ├── rag/
│   │   │   ├── bm25_retriever.py     # Lexical search engine
│   │   │   ├── embeddings.py         # SentenceTransformers service
│   │   │   ├── generation.py         # Clinical response synthesis
│   │   │   ├── llm/                  # LLM provider adapters (Mistral, OpenAI, Local)
│   │   │   ├── prompts.py            # Clinical prompts & triage instructions
│   │   │   ├── retriever.py          # Hybrid retrieval coordinator
│   │   │   └── vector_store.py       # ChromaDB vector store wrapper
│   │   ├── schemas/                  # Pydantic request/response models
│   │   └── main.py                   # FastAPI application factory & lifespan
│   ├── ingestion/
│   │   ├── chunker.py                # Clinical chunking & section splitter
│   │   ├── models.py                 # Ingestion data structures
│   │   └── pdf_loader.py             # PyMuPDF parser & metadata extractor
│   └── requirements.txt              # Production Python dependencies
├── data/
│   ├── raw/                          # Official ICMR PDF guidelines
│   ├── processed/                    # Extracted chunks (icmr_clinical_chunks.json)
│   └── metadata/                     # Guideline catalog & taxonomies
├── frontend/
│   ├── index.html                    # Clinical web dashboard
│   ├── css/                          # Glassmorphism healthcare UI styling
│   └── js/                           # Client chat & workflow accordion logic
├── scripts/
│   ├── run_ingestion.py              # Ingests raw PDFs into structured text
│   ├── run_chunking.py               # Generates clinical chunks with metadata
│   ├── run_indexing.py               # Indexes chunks into ChromaDB
│   └── query_clinical_workflow.py    # Terminal CLI for clinical workflows
├── vector_db/                        # Local ChromaDB persistent storage
├── .env.example                      # Template environment variables
├── .gitignore                        # Git exclusion rules
└── README.md                         # Project documentation
```

---

## 5. Getting Started

### 5.1 Prerequisites

- **Python 3.10+**
- **Git**
- *(Optional)* An API key from [Mistral AI](https://console.mistral.ai/) or [OpenAI](https://platform.openai.com/)

---

### 5.2 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/<your-username>/medical-llm.git
   cd medical-llm
   ```

2. **Create and activate a virtual environment**:
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS (Bash)**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r backend/requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   # Windows PowerShell
   Copy-Item .env.example .env

   # Linux / macOS
   cp .env.example .env
   ```

   Open `.env` and set your preferred LLM provider and credentials:
   ```ini
   LLM_PROVIDER="mistral"
   MISTRAL_API_KEY="your-mistral-api-key-here"
   MISTRAL_MODEL="ministral-8b-latest"

   # Vector Database (Local ChromaDB for ultra-low latency)
   CHROMA_USE_CLOUD=False
   CHROMA_PERSIST_DIRECTORY="./vector_db"
   ```

---

### 5.3 Running the Application

Start the FastAPI server and clinical dashboard:

```powershell
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Once running, access the interfaces in your browser:

| Interface | URL | Description |
|---|---|---|
| **Clinical Web Dashboard** | [http://localhost:8000/](http://localhost:8000/) or [http://localhost:8000/ui](http://localhost:8000/ui) | Full interactive conversational triage & workflow UI |
| **Interactive API Docs (Swagger)** | [http://localhost:8000/docs](http://localhost:8000/docs) | Test and explore all REST API endpoints |
| **Alternative Docs (ReDoc)** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Clean, searchable API documentation |
| **System Health Check** | [http://localhost:8000/api/health](http://localhost:8000/api/health) | Real-time status of database and vector stores |

---

## 6. Offline Data Pipeline (Ingestion & Indexing)

If you add new ICMR STW PDF files to `data/raw/` or wish to re-index the dataset:

```powershell
# 1. Parse raw ICMR STW PDFs and extract text
python scripts/run_ingestion.py

# 2. Chunk text with section classification and metadata tagging
python scripts/run_chunking.py

# 3. Embed chunks and index into local ChromaDB
python scripts/run_indexing.py

# 4. Run a clinical query via the command-line CLI
python scripts/query_clinical_workflow.py "First-line therapy for adult hypertension"
```

---

## 7. API Reference

### `POST /api/chat`
Conversational symptom triage endpoint with medical scope guardrails.

**Sample Request**:
```json
{
  "message": "Adult patient presenting with persistent BP 152/96 mmHg on repeat office readings",
  "patient_vitals": "BP: 152/96 mmHg, Pulse: 78 bpm, BMI: 27.2",
  "history": []
}
```

**Sample Response**:
```json
{
  "reply": "According to the ICMR Standard Treatment Workflow for Hypertension in Adults, a blood pressure of 152/96 mmHg confirms Stage 1/2 Hypertension. Non-pharmacological lifestyle interventions must be initiated immediately alongside first-line monotherapy.",
  "urgency_level": "ROUTINE",
  "condition_matched": "Hypertension in Adults",
  "specialty": "Cardiology",
  "relevant_stw": "Hypertension in Adults",
  "red_flags": [
    "Systolic BP >= 180 or Diastolic BP >= 120 mmHg (Hypertensive Emergency)",
    "Severe headache, visual disturbances, chest pain, or dyspnea"
  ],
  "immediate_actions": [
    "Confirm BP elevation across multiple readings.",
    "Initiate dietary sodium restriction to < 5g per day.",
    "Target minimum 30 minutes of moderate aerobic activity 5 days weekly."
  ],
  "workflow_steps": [
    {
      "step_number": 1,
      "phase": "Initial Assessment",
      "title": "Baseline Cardiovascular Evaluation",
      "description": "Assess cardiovascular risk factors, target organ damage, and secondary causes.",
      "page_reference": 2
    },
    {
      "step_number": 2,
      "phase": "Management",
      "title": "First-Line Pharmacotherapy",
      "description": "Start with a low-dose Thiazide diuretic, ACE-inhibitor/ARB, or Calcium Channel Blocker.",
      "page_reference": 4
    }
  ],
  "evidence": [
    {
      "stw_title": "Hypertension in Adults",
      "specialty": "Cardiology",
      "page_number": 4,
      "relevance_score": 0.88
    }
  ]
}
```

### `POST /api/query`
Direct clinical decision support endpoint returning formal ICMR workflow stages and citations.

### `GET /api/stws`
Returns the full catalog of indexed ICMR STW documents, diseases, and specialties.

### `GET /api/health`
Returns operational telemetry, database connection status, and vector store configuration.

---

## 8. Configuration Reference (`.env`)

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | Deployment environment (`development` / `production`) |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL / Supabase connection URI (falls back to SQLite) |
| `CHROMA_USE_CLOUD` | `False` | Use `False` for ultra-fast local ChromaDB (`./vector_db`) |
| `CHROMA_PERSIST_DIRECTORY` | `./vector_db` | Local directory for ChromaDB vector embeddings |
| `EMBEDDING_MODEL_NAME` | `all-MiniLM-L6-v2` | SentenceTransformers model for dense clinical embeddings |
| `LLM_PROVIDER` | `mistral` | Active provider: `mistral`, `openai`, `groq`, or `local` |
| `MISTRAL_API_KEY` | - | API key for Mistral AI |
| `MISTRAL_MODEL` | `ministral-8b-latest` | Mistral model identifier |
| `RETRIEVAL_TOP_K` | `3` | Number of evidence chunks retrieved per query |
| `ENABLE_HYBRID_RETRIEVAL` | `True` | Fuses dense vector similarity with BM25 keyword matching |
| `GROUNDING_STRICT_MODE` | `True` | Enforces citation requirements and evidence validation |

---

## 9. Security & Privacy

- **PHI Redaction**: Built-in regex filters (`mask_sensitive_phi`) strip patient identifiers (names, Aadhaar numbers, phone numbers, email addresses) before sending queries to LLM providers.
- **Header Protection**: Standard security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-Clinical-Safety`) are injected on every HTTP response.
- **Git Security**: Secrets, `.env` files, and virtual environments are explicitly excluded via `.gitignore`.

---

## 10. License & Citation

This project is licensed under the **MIT License**.

If you use this platform in your clinical research, please cite the official ICMR guidelines:
> *Indian Council of Medical Research (ICMR). Standard Treatment Workflows (STWs) for Management of Common Diseases. Government of India.*  
> Repository: [https://www.icmr.gov.in/standard-treatment-workflows-stws](https://www.icmr.gov.in/standard-treatment-workflows-stws)
