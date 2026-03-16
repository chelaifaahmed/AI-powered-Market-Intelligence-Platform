"""Operational runner for NLP pipeline tasks."""

from __future__ import annotations

from database.connection import get_db_session
from nlp.nlp_pipeline import NlpPipeline


def main() -> None:
    try:
        with get_db_session() as session:
            pipeline = NlpPipeline(session=session)

            print("[NLP] Starting car reviews NLP processing...")
            car_metrics = pipeline.process_car_reviews(limit=500)
            print("[NLP] Car reviews completed")
            print(car_metrics)

            print("[NLP] Starting insurance reviews NLP processing...")
            insurance_metrics = pipeline.process_insurance_reviews(limit=500)
            print("[NLP] Insurance reviews completed")
            print(insurance_metrics)

            print("[NLP] Starting market articles NLP processing...")
            article_metrics = pipeline.process_articles(limit=500)
            print("[NLP] Market articles completed")
            print(article_metrics)

        print("[NLP] Pipeline execution finished")
    except Exception as exc:
        print(f"[NLP] Pipeline execution failed: {exc}")


if __name__ == "__main__":
    main()
