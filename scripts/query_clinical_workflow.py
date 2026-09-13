import argparse
import logging
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from backend.app.rag.generation import RAGGenerator
from backend.app.rag.llm.factory import get_llm_provider
from backend.app.database.session import SessionLocal
from backend.app.models.query_log import ClinicalQueryLog, QuerySource
from backend.app.models.specialty import Specialty
from backend.app.models.disease import Disease
from backend.app.models.stw_document import STWDocument

logging.basicConfig(level=logging.WARNING)


def format_clinical_response(response, execution_time_s: float):
    print("\n" + "=" * 75)
    print("🏥 ICMR CLINICAL WORKFLOW INTELLIGENCE REPORT")
    print("=" * 75)
    print(f"Condition:        {response.disease or 'N/A'} ({response.specialty or 'General'})")
    print(f"Official STW:     {response.relevant_stw}")
    print(f"Inference Time:   {execution_time_s:.2f}s")
    print("-" * 75)
    print("📋 CLINICAL GUIDELINE SUMMARY:")
    print(response.summary)
    print("-" * 75)

    if response.workflow_steps:
        print(f"⚡ WORKFLOW STEPS ({len(response.workflow_steps)} stages):")
        for s in response.workflow_steps:
            print(f"\n  [Step {s.step_number}] Phase: {s.phase} (ICMR Page {s.page_reference})")
            print(f"  Title:  {s.title}")
            print(f"  Action: {s.description}")
        print("-" * 75)

    if response.evidence:
        print(f"📚 AUTHORITATIVE CITATIONS ({len(response.evidence)} excerpts):")
        for ev in response.evidence:
            print(f"\n  • [{ev.chunk_id}] (Score: {ev.similarity_score:.4f}, Page {ev.page}):")
            print(f"    \"{ev.retrieved_evidence}\"")
        print("-" * 75)

    if response.limitations:
        print("⚠️ HEALTHCARE TIER CONSIDERATIONS & LIMITATIONS:")
        for lim in response.limitations:
            print(f"  * {lim}")
        print("-" * 75)

    print("🛡️ SAFETY NOTICE:")
    print(response.safety_notice)
    print("=" * 75 + "\n")


def log_to_supabase(query: str, response, latency_ms: float):
    """Saves query and citations to Supabase PostgreSQL audit tables."""
    try:
        with SessionLocal() as db:
            spec = db.query(Specialty).filter(Specialty.name.ilike(f"%{response.specialty}%")).first() if response.specialty else None
            dis = db.query(Disease).filter(Disease.name.ilike(f"%{response.disease}%")).first() if response.disease else None
            doc = db.query(STWDocument).filter(STWDocument.title.ilike(f"%{response.relevant_stw}%")).first() if response.relevant_stw else None

            log_entry = ClinicalQueryLog(
                query_text=query,
                specialty_id=spec.id if spec else None,
                disease_id=dis.id if dis else None,
                retrieved_stw_id=doc.id if doc else None,
                response_summary=response.summary[:1000] if response.summary else "",
                llm_provider="mistral",
                latency_ms=round(latency_ms, 2),
                is_grounded=bool(response.evidence)
            )
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)

            for ev in response.evidence:
                qs = QuerySource(
                    query_log_id=log_entry.id,
                    stw_document_id=doc.id if doc else 1,
                    chunk_id=ev.chunk_id,
                    page_number=ev.page,
                    section=response.specialty or "General",
                    similarity_score=ev.similarity_score,
                    excerpt=ev.retrieved_evidence[:500]
                )
                db.add(qs)
            db.commit()
    except Exception as db_err:
        pass


def execute_query(generator: RAGGenerator, query: str, specialty: str = None, disease: str = None, context: str = None):
    start = time.time()
    response = generator.generate_response(
        query=query,
        specialty=specialty,
        disease=disease,
        patient_context=context
    )
    duration = time.time() - start
    format_clinical_response(response, duration)
    log_to_supabase(query, response, duration * 1000)


def interactive_mode(generator: RAGGenerator):
    print("\n" + "=" * 75)
    print("🩺 ICMR-STW CLINICAL WORKFLOW INTELLIGENCE (LIVE CLI)")
    print("Grounded in official ICMR guidelines | Powered by Mistral AI & Chroma Cloud")
    print("Type 'exit' or 'quit' to exit.")
    print("=" * 75)

    while True:
        try:
            print("\nEnter your clinical query (e.g. 'How to treat hyperkalemia in AKI?'):")
            query = input("Clinical Query > ").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit", "q"]:
                print("Exiting. Have a great day!")
                break

            print("(Optional) Patient context / lab values (Press Enter to skip):")
            context = input("Patient Context > ").strip() or None

            print("(Optional) Specialty filter (e.g. 'Nephrology', 'Cardiology', Press Enter to skip):")
            spec = input("Specialty Filter > ").strip() or None

            print("\n🔍 Retrieving from Chroma Cloud and generating with Mistral AI...")
            execute_query(generator, query=query, specialty=spec, context=context)

        except (KeyboardInterrupt, EOFError):
            print("\nSession ended.")
            break


def main():
    parser = argparse.ArgumentParser(description="Query ICMR Clinical Workflow Intelligence System with Real Data")
    parser.add_argument("-q", "--query", type=str, help="Clinical query text")
    parser.add_argument("-s", "--specialty", type=str, default=None, help="Filter by specialty (e.g. Nephrology, Cardiology)")
    parser.add_argument("-d", "--disease", type=str, default=None, help="Filter by disease (e.g. Acute Kidney Injury)")
    parser.add_argument("-c", "--context", type=str, default=None, help="Patient context, vitals, or lab parameters")

    args = parser.parse_args()

    llm = get_llm_provider("mistral")
    generator = RAGGenerator(llm_provider=llm)

    if args.query:
        execute_query(generator, query=args.query, specialty=args.specialty, disease=args.disease, context=args.context)
    else:
        interactive_mode(generator)


if __name__ == "__main__":
    main()
