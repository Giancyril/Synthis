import json
from unittest.mock import MagicMock
from src.models.schemas import Source, ComparisonDimension, ComparativeReport
from src.pipeline.comparative_pipeline import ComparativePipeline


def _make_source(sid: str, url: str) -> Source:
    return Source(
        id=sid, url=url, title=f"Title {sid}",
        snippet=f"Snippet for {sid}", summary=f"Summary {sid}",
    )


def test_infer_dimensions_parses_json():
    pipeline = ComparativePipeline.__new__(ComparativePipeline)
    pipeline.gemini_svc = MagicMock()
    pipeline.gemini_svc.generate_text.return_value = '["Cost", "Performance", "Ecosystem", "Scalability"]'

    dims = pipeline._infer_dimensions("React", "Vue")
    assert dims == ["Cost", "Performance", "Ecosystem", "Scalability"]


def test_infer_dimensions_fallback_on_bad_json():
    pipeline = ComparativePipeline.__new__(ComparativePipeline)
    pipeline.gemini_svc = MagicMock()
    pipeline.gemini_svc.generate_text.return_value = "not valid json at all"

    dims = pipeline._infer_dimensions("React", "Vue")
    assert isinstance(dims, list)
    assert len(dims) >= 1  # fallback dimensions always returned


def test_synthesize_batch_validates_citations():
    pipeline = ComparativePipeline.__new__(ComparativePipeline)
    pipeline.gemini_svc = MagicMock()
    pipeline.gemini_svc.generate_text.return_value = json.dumps([
        {
            "dimension_name": "Ecosystem",
            "topic_a_position": "React has a large ecosystem [S1].",
            "topic_a_source_ids": ["S1"],
            "topic_b_position": "Vue is more approachable [S2].",
            "topic_b_source_ids": ["S2"],
            "verdict_or_note": None,
        }
    ])

    a_sources = [_make_source("S1", "https://react.dev/1")]
    b_sources = [_make_source("S2", "https://vuejs.org/2")]

    dims = pipeline._synthesize_batch(
        "React", "Vue", ["Ecosystem"], a_sources, b_sources
    )

    assert len(dims) == 1
    dim = dims[0]
    assert dim.dimension_name == "Ecosystem"
    assert "[S1]" in dim.topic_a_position
    assert "[S2]" in dim.topic_b_position
    assert dim.verdict_or_note is None
