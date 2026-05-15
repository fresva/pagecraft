"""Unit tests for the renderer's annotation support."""
from pagecraft.mcp_server.renderer import wrap_annotated, apply_annotations


def test_wrap_annotated_verify():
    result = wrap_annotated("50%", "value", "Check this", "verify")
    assert 'annotation-verify' in result
    assert 'data-annotation-severity="verify"' in result
    assert "Check this" in result
    assert "50%" in result


def test_wrap_annotated_assumption():
    result = wrap_annotated("Data", "field", "Assumed", "assumption")
    assert 'annotation-assumption' in result


def test_wrap_annotated_missing():
    result = wrap_annotated("???", "field", "Need input", "missing")
    assert 'annotation-missing' in result


def test_wrap_annotated_escapes_html():
    result = wrap_annotated('<script>alert("xss")</script>', "f", "Test", "verify")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_wrap_annotated_escapes_annotation_text():
    result = wrap_annotated("val", "f", 'Text with "quotes" & <tags>', "verify")
    assert '"quotes"' not in result or "&quot;" in result
    assert "<tags>" not in result


def test_apply_annotations_modifies_matching_fields():
    data = {"title": "Hello", "body": "World"}
    annotations = [{"field": "title", "text": "Check title", "severity": "verify"}]
    result = apply_annotations(data, annotations)
    assert "annotation-verify" in result["title"]
    assert result["body"] == "World"  # Unchanged


def test_apply_annotations_none():
    data = {"title": "Hello"}
    result = apply_annotations(data, None)
    assert result["title"] == "Hello"


def test_apply_annotations_empty_list():
    data = {"title": "Hello"}
    result = apply_annotations(data, [])
    assert result["title"] == "Hello"


def test_apply_annotations_no_matching_field():
    data = {"title": "Hello"}
    annotations = [{"field": "nonexistent", "text": "Check", "severity": "verify"}]
    result = apply_annotations(data, annotations)
    assert result["title"] == "Hello"
