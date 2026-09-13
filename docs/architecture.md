# ICMR-STW AI: System Architecture

## 1. Executive Summary

The **ICMR-Guided Clinical Workflow Intelligence System (ICMR-STW AI)** is an evidence-grounded clinical decision-support and educational platform. It transforms the Indian Council of Medical Research (ICMR) Standard Treatment Workflows (STWs) from static, multi-page PDFs into structured, searchable, interactive, and verifiable clinical guidance.

## 2. High-Level System Architecture

```
                                  [ Official ICMR STW Documents ]
                                                 │
                                                 ▼
                                        [ Ingestion Pipeline ]
                                        (PyMuPDF / pdfplumber)
                                                 │
                                                 ▼
                                    [ Text Cleaning & Chunking ]
                                 (Section identification, metadata)
                                                 │
                                                 ▼
                                    [ Dual Storage Architecture ]
                                    ┌────────────┴────────────┐
                                    ▼                         ▼
                          [ PostgreSQL / SQLite ]         [ ChromaDB ]
                          (Entities, Workflows,         (Embeddings, Chunks,
                           Audit Logs, Metadata)         Source Attributions)
                                    │                         │
                                    └────────────┬────────────┘
                                                 │
                                                 ▼
                                     [ Hybrid Retrieval Engine ]
                                     (Dense Vectors + BM25 + Filters)
                                                 │
                                                 ▼
                                  [ LLM / SLM Abstraction Layer ]
                               (OpenAI / Groq / Local SLM / Offline Mock)
                                                 │
                                                 ▼
                                  [ Clinical Grounding & Safety ]
                               (Strict ICMR Citations & Anti-Hallucination)
                                                 │
                                                 ▼
                                     [ FastAPI REST Services ]
                                                 │
                                                 ▼
                                [ Modern Next.js / React Frontend ]
```

## 3. Core Architectural Modules

### 3.1 Document Ingestion & Section Parser
- **Source**: Authoritative ICMR STW PDFs across volumes (Medicine, Nephrology, Cardiology, etc.).
- **Extraction**: PyMuPDF (`fitz`) handles high-throughput extraction; OCR fallback via `pytesseract` handles scanned sections.
- **Section Tagger**: Classifies medical sections: Initial Assessment, Diagnostic Investigations, Management/Treatment, Follow-up, and Referral Triggers.

### 3.2 Dual-Storage Architecture
1. **Relational Database (PostgreSQL / SQLite fallback)**:
   - Tracks canonical medical hierarchy: Specialties, Diseases, STW Documents, and Structured Workflow Steps.
   - Maintains query audit logs, source linkages, and user feedback.
2. **Vector Database (ChromaDB)**:
   - Stores dense embeddings generated via Sentence Transformers (`all-MiniLM-L6-v2`).
   - Retains granular metadata: document ID, specialty, disease, volume, section, page number, and chunk ID.

### 3.3 Hybrid Retrieval Engine
- Combines dense semantic similarity search with BM25 keyword matching (weighted reciprocal rank fusion).
- Applies clinical filters (specialty, disease code, clinical section).
- Enforces strict relevance thresholds to prevent out-of-context or misleading citations.

### 3.4 Provider-Agnostic LLM/SLM Interface
- Pluggable adapter pattern (`LLMProvider`) supporting:
  - **OpenAI** (e.g., `gpt-4o-mini`, `gpt-4o`)
  - **Groq** (e.g., `llama-3.1-8b-instant`)
  - **Local SLM** (Ollama / vLLM with `qwen2.5:7b`, `llama-3.2:3b`)
  - **Mock / Offline Provider** (for automated testing and air-gapped deterministic validation)

### 3.5 Grounding & Safety Guardrail
- Mandates that every clinical assertion is traced to an explicit page and chunk in the ICMR STWs.
- Automatically triggers a structured refusal if retrieved evidence is below clinical threshold:
  *"Insufficient ICMR evidence was retrieved to answer this safely."*
- Prohibits autonomous prescription or replacing qualified medical personnel.
