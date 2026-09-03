from partgraph.collectors.staging import CandidateType
from partgraph.collectors.unstructured import SourceDocument, source_document_observation


def test_unstructured_document_preserves_source_and_extraction_separately():
    document = SourceDocument(
        source_record_id="page-123",
        source_url="https://example.test/parts/123",
        content="<html><body>Fits 2012 Honda Civic EX</body></html>",
        content_type="text/html",
        title="Example part",
        metadata={"http_status": 200},
    )

    observation = source_document_observation(
        document,
        provider="example",
        dataset="parts_pages",
        extracted_candidate={"part_number": "ABC-123", "trim": "EX"},
        vehicle_identity={"year": 2012, "make": "Honda", "model": "Civic"},
        extraction_method="parser-v1",
    )

    assert observation.candidate_type == CandidateType.SOURCE_DOCUMENT
    assert observation.raw_payload["content"] == document.content
    assert observation.raw_payload["content_type"] == "text/html"
    assert observation.candidate_payload == {"part_number": "ABC-123", "trim": "EX"}
    assert observation.vehicle_identity["model"] == "Civic"
    assert observation.provenance == {"provider": "example", "dataset": "parts_pages"}
    assert observation.extraction_method == "parser-v1"
