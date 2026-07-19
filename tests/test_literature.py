from __future__ import annotations

from aie_ddxbench_construction.literature import (
    SearchHit,
    extract_first_doi,
    normalize_doi,
    resolve_hits,
    run_literature_retrieval,
    search_mechanism,
    title_similarity,
)


class SearchFixture:
    def search(self, *, query: str, max_results: int, search_depth: str):
        return [
            {
                "title": "Example molecular photophysics paper",
                "url": "https://doi.org/10.1000/Example.1",
                "content": "A synthetic search fixture.",
            }
        ]


def test_normalize_and_extract_doi() -> None:
    assert normalize_doi("https://doi.org/10.1000/Example.1.") == "10.1000/example.1"
    assert extract_first_doi("See DOI: 10.1000/Example.1 for details.") == "10.1000/example.1"


def test_mechanism_search_keeps_bucket_as_retrieval_metadata() -> None:
    hits = search_mechanism("RACI_CI_ACCESS", client=SearchFixture(), max_results=1)
    assert hits
    assert all(hit.retrieval_mechanism == "RACI_CI_ACCESS" for hit in hits)
    assert all(hit.visible_doi == "10.1000/example.1" for hit in hits)


def test_visible_doi_resolution_deduplicates_hits_without_network() -> None:
    hits = [
        SearchHit("RIM_RIR_RIV", "q1", "Title", "https://doi.org/10.1000/x", "", "10.1000/x", 1),
        SearchHit("ICT_TICT_CT", "q2", "Title", "https://example.test", "10.1000/X", "10.1000/x", 1),
    ]
    records, unresolved = resolve_hits(hits)
    assert unresolved == []
    assert len(records) == 1
    assert records[0].retrieval_mechanisms == ("ICT_TICT_CT", "RIM_RIR_RIV")


def test_title_similarity_is_normalized() -> None:
    assert title_similarity("A Study: of Emission", "A study of emission") == 1.0


def test_retrieval_batch_persists_intermediate_artifacts(tmp_path) -> None:
    summary = run_literature_retrieval(
        "RACI_CI_ACCESS",
        client=SearchFixture(),
        output_dir=tmp_path,
        max_results=1,
        max_queries=1,
        resolve_unlisted_dois=False,
    )

    assert summary["query_count"] == 1
    assert summary["resolved_doi_count"] == 1
    assert (tmp_path / "queries.json").is_file()
    assert (tmp_path / "query_results" / "001.json").is_file()
    assert (tmp_path / "search_hits.json").is_file()
    assert (tmp_path / "resolved_doi_records.json").is_file()
    assert (tmp_path / "unresolved_hits.json").is_file()
    assert (tmp_path / "retrieval_summary.json").is_file()
