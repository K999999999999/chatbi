"""Business Analysis 报告增量 JSON 解码边界。"""

import pytest

from src.business_analysis.report_stream import IncrementalReportJSONDecoder


def test_decoder_streams_only_allowlisted_text_and_preserves_list_indices():
    decoder = IncrementalReportJSONDecoder()
    chunks = [
        '{"title":"毛',
        "利\\u5b9e",
        '时 😀","extra":{"title":"不可见"},"key_findings":["一',
        '项\\n发现", "\\uD83D',
        '\\uDE00"],"executive_summary":"摘要","trend_judgment":"稳定",',
        '"root_causes":[],"action_suggestions":[],"evidence_task_ids":[],',
        '"incomplete_tasks":[]}',
    ]

    deltas = [delta for chunk in chunks for delta in decoder.feed(chunk)]
    decoder.finish()

    assert [(item.field, item.index, item.offset, item.text) for item in deltas] == [
        ("title", None, 0, "毛"),
        ("title", None, 1, "利实"),
        ("title", None, 3, "时 😀"),
        ("key_findings", 0, 0, "一"),
        ("key_findings", 0, 1, "项\n发现"),
        ("key_findings", 1, 0, "😀"),
        ("executive_summary", None, 0, "摘要"),
        ("trend_judgment", None, 0, "稳定"),
    ]


def test_decoder_rejects_duplicate_keys_and_unpaired_surrogates():
    duplicate = IncrementalReportJSONDecoder()
    with pytest.raises(ValueError):
        duplicate.feed('{"title":"旧","title":"新"}')

    unpaired = IncrementalReportJSONDecoder()
    with pytest.raises(ValueError):
        unpaired.feed('{"title":"\\uD800"}')


def test_decoder_rejects_malformed_json_without_emitting_unknown_nested_text():
    decoder = IncrementalReportJSONDecoder()
    deltas = decoder.feed('{"extra":{"title":"不可见"},"title":"安全"')

    assert [(item.field, item.text) for item in deltas] == [("title", "安全")]
    with pytest.raises(ValueError):
        decoder.finish()


def test_decoder_caps_public_draft_bytes_without_truncating():
    decoder = IncrementalReportJSONDecoder(max_draft_bytes=3)
    assert decoder.feed('{"title":"abc')[0].text == "abc"
    with pytest.raises(ValueError, match="公开上限"):
        decoder.feed("d")
