# ICMR-STW AI: Vector Embeddings & Hybrid Retrieval Architecture

## 1. Overview

The Retrieval-Augmented Generation (RAG) subsystem of **ICMR-STW AI** transforms standardized clinical workflow chunks into high-dimensional semantic vector spaces. It powers evidence-grounded clinical search and decision support derived exclusively from official **Indian Council of Medical Research (ICMR)** STW guidelines.

---

## 2. Vector Embedding Architecture

- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Dimensionality**: 384 dimensions
- **Normalization**: Unit L2 normalization ($||\mathbf{v}||_2 = 1.0$)
- **Similarity Metric**: Cosine distance ($d_{cos} \in [0, 2]$), mapped to similarity score ($s = 1 - d_{cos} \in [0, 1]$).
- **Context Injection**: Each chunk combines an explicit medical context breadcrumb with pure guideline text:
  ```
  [ICMR STW: {disease} | Specialty: {specialty} | Section: {section_title} ({section_type}) | Page: {page_number}]
  {guideline_content}
  ```

---

## 3. ChromaDB Configuration & Dual-Mode Deployment

The system supports both **Chroma Cloud** (remote managed cluster) and **Local ChromaDB** (disk persistence in `vector_db/`):

### 3.1 Cloud Configuration
Configured via `.env`:
```env
CHROMA_USE_CLOUD=True
CHROMA_API_KEY="<your_chroma_api_key>"
CHROMA_TENANT="<your_tenant_id>"
CHROMA_DATABASE="<your_database_name>"
CHROMA_COLLECTION_NAME="icmr_stw_chunks"
```

### 3.2 Offline / Local Fallback
When `CHROMA_USE_CLOUD=False` or if network issues occur, the vector store automatically falls back to local persistence:
```python
chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIRECTORY)
```

---

## 4. Indexed Metadata Schema

Every vector in the `icmr_stw_chunks` collection carries granular clinical metadata:

| Metadata Field | Type | Description | Example |
|---|---|---|---|
| `chunk_id` | `str` | Unique deterministic identifier | `ICMR-NEPHRO-ACUTEKID-P01-C007` |
| `specialty` | `str` | ICMR clinical specialty | `Nephrology`, `Cardiology` |
| `disease` | `str` | Disease / condition name | `Acute Kidney Injury` |
| `stw_title` | `str` | Full guideline title | `ICMR STW: Acute Kidney Injury` |
| `volume` | `str` | ICMR publication volume | `Volume 1` |
| `section_title` | `str` | Clinical section heading | `Treatment Of Hyperkalemia` |
| `section_type` | `str` | Standardized clinical category | `MANAGEMENT`, `INVESTIGATION`, `RED_FLAGS` |
| `page_number` | `int` | Exact page in official PDF | `1` |
| `source_url` | `str` | Official ICMR web URL | `https://www.icmr.gov.in/...` |
| `file_name` | `str` | Source PDF filename | `1784807239_acutekidneyinjury-updated.pdf` |
| `char_count` | `int` | Character count of content | `421` |

---

## 5. Hybrid Retrieval Engine (Phase 5)

The retrieval engine combines dense semantic search and BM25 lexical keyword matching using a weighted score fusion mechanism:

$$\text{Relevance Score} = (w_{dense} \cdot s_{dense}) + (w_{bm25} \cdot s_{bm25})$$

where:
- $w_{dense} = 0.60$ (default semantic weight)
- $w_{bm25} = 0.40$ (default lexical keyword weight)

### 5.1 Metadata Filtering & Guardrails
- **Clinical Constraints**: Queries can be filtered by `specialty`, `disease`, and `section_type` (e.g. only search `MANAGEMENT` steps for `Acute Kidney Injury`).
- **Relevance Thresholding**: Queries with fused scores below `settings.RETRIEVAL_RELEVANCE_THRESHOLD` (default `0.35`) are flagged as insufficient evidence (`is_above_threshold = False`) to prevent hallucinations on unsupported or out-of-domain questions.

### 5.2 Python Retrieval API
```python
from backend.app.rag.retriever import HybridClinicalRetriever

retriever = HybridClinicalRetriever()
evidence_list = retriever.retrieve(
    query="indications for urgent dialysis in acute kidney injury",
    top_k=3,
    specialty="Nephrology"
)

for ev in evidence_list:
    print(f"[{ev.relevance_score:.4f}] {ev.stw_title} (Page {ev.page_number}) - {ev.section_title}")
    print(f"Content: {ev.content}")
```

---

## 6. LLM & SLM Multi-Provider Architecture (Phase 6)

The generation subsystem bridges hybrid retrieval evidence to structured clinical workflows. It is architected around an extensible `LLMProvider` abstraction supporting cloud LLMs, local SLMs, and offline deterministic engines.

### 6.1 Supported Providers

| Provider Key | Class | Supported Models | Description |
|---|---|---|---|
| `mock` | `MockLLMProvider` | `mock-clinical-engine` | Offline, deterministic extractor. Formats grounded responses directly from ICMR chunks without API keys. |
| `openai` | `OpenAIProvider` | `gpt-4o-mini`, `gpt-4o` | Cloud-hosted OpenAI models with native `response_format={"type": "json_object"}`. |
| `groq` | `GroqProvider` | `llama-3.1-8b-instant`, `llama-3.3-70b-versatile` | Ultra-fast inference provider with native JSON schema enforcement. |
| `local` | `LocalSLMProvider` | `qwen2.5:7b`, `llama3.2:3b`, `mistral:7b` | On-premise / edge deployment via Ollama, vLLM, or LM Studio with OpenAI-compatible endpoints. |

### 6.2 Provider Switching via Configuration

Switching providers is accomplished dynamically through `.env`:
```env
# Example: Using Groq LLaMA-3.1
LLM_PROVIDER="groq"
GROQ_API_KEY="gsk_..."
GROQ_MODEL="llama-3.1-8b-instant"

# Example: Using Local Ollama SLM
LLM_PROVIDER="local"
LOCAL_SLM_BASE_URL="http://localhost:11434/v1"
LOCAL_SLM_MODEL="qwen2.5:7b"
```

---

## 7. Clinical Prompt Engineering & Guardrails

The system prompt enforces strict clinical constraints to prevent diagnostic overreach or extrapolation beyond the ICMR STWs:

```
You are the ICMR Clinical Workflow Intelligence Engine, an authoritative,
evidence-grounded clinical decision-support and standard treatment workflow assistant.

CORE MANDATE:
- Ground every statement strictly in the provided official ICMR Standard Treatment Workflows.
- Do NOT hallucinate medications, dosages, or procedures not present in the retrieved evidence.
- You are a clinical decision-support tool, NOT an autonomous doctor.
- When evidence is insufficient, state clearly: "Insufficient ICMR evidence was retrieved."
```

### 7.1 Structured Response Schema

The generator parses and guarantees output conforming to `ClinicalQueryResponse`:
- **Summary**: Concise clinical guideline synopsis.
- **Workflow Steps**: Step-by-step actions (`Initial Assessment`, `Investigation`, `Management`, `Referral`, `Follow-up`) with exact ICMR page numbers.
- **Evidence Citations**: Granular chunks (`chunk_id`, `similarity_score`, `page`, excerpt).
- **Source References**: Official STW document title, volume, and URL.
- **Limitations**: Healthcare tier feasibility caveats (Primary, Secondary, Tertiary care constraints).
- **Safety Disclaimer**: Prominent statutory non-autonomous clinical disclaimer.

