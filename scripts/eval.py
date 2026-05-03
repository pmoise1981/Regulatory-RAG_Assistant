import argparse
import json
import re
from pathlib import Path
from statistics import mean

from app.api.main import extractive_answer, lexical_chunk_search


CITATION_RE = re.compile(r"\[[^\]]+::[^\]]+\]")


def load_cases(path: Path) -> list[dict]:
    cases = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cases.append(json.loads(line))
    return cases


def evaluate_case(case: dict, top_k: int) -> dict:
    query = case["query"]
    expected_sources = set(case.get("expected_sources", []))
    required_terms = [term.lower() for term in case.get("required_terms", [])]

    hits = lexical_chunk_search(query, top_k=top_k)
    sources = [h.get("metadata", {}).get("source", "") for h in hits]
    source_set = set(sources)
    answer = extractive_answer(query, hits)
    answer_l = answer.lower()

    source_recall = 1.0
    if expected_sources:
        source_recall = len(expected_sources & source_set) / len(expected_sources)

    term_coverage = 1.0
    if required_terms:
        term_coverage = sum(term in answer_l for term in required_terms) / len(required_terms)

    citation_present = bool(CITATION_RE.search(answer))
    passed = source_recall >= 1.0 and term_coverage >= 0.6 and citation_present

    return {
        "name": case.get("name", query[:60]),
        "query": query,
        "passed": passed,
        "source_recall": round(source_recall, 3),
        "term_coverage": round(term_coverage, 3),
        "citation_present": citation_present,
        "retrieved_sources": sources,
    }


def main():
    parser = argparse.ArgumentParser(description="Offline retrieval and citation evals for Regulatory RAG.")
    parser.add_argument("--dataset", default="eval/datasets/regulatory_smoke.jsonl")
    parser.add_argument("--top-k", type=int, default=6)
    args = parser.parse_args()

    dataset = Path(args.dataset)
    if not dataset.exists():
        raise SystemExit(f"Dataset not found: {dataset}")

    results = [evaluate_case(case, args.top_k) for case in load_cases(dataset)]
    summary = {
        "cases": len(results),
        "passed": sum(r["passed"] for r in results),
        "pass_rate": round(sum(r["passed"] for r in results) / max(1, len(results)), 3),
        "avg_source_recall": round(mean(r["source_recall"] for r in results), 3) if results else 0,
        "avg_term_coverage": round(mean(r["term_coverage"] for r in results), 3) if results else 0,
    }
    print(json.dumps({"summary": summary, "results": results}, indent=2))
    if summary["passed"] != summary["cases"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
