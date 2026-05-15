"""Shared HTML rendering logic for MCP tools.

Each tool calls render_component() which loads a Jinja2 template
and embeds annotations as data attributes.
"""
import html as html_module
from pathlib import Path

from jinja2 import ChainableUndefined, Environment, FileSystemLoader

_templates_dir = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(_templates_dir),
    undefined=ChainableUndefined,
)


def render_component(template_name: str, data: dict) -> str:
    """Render a component template with the given data."""
    template = _jinja_env.get_template(template_name)
    return template.render(**data)


def wrap_annotated(value: str, field: str, text: str, severity: str) -> str:
    """Wrap a value in an annotation span with data attributes.

    Returns the value wrapped in a <span> with annotation metadata,
    or the raw value if no annotation is needed.
    """
    severity_class = f"annotation-{severity}"
    escaped_text = html_module.escape(text)
    escaped_value = html_module.escape(str(value))
    return (
        f'<span class="annotated {severity_class}" '
        f'data-annotation-field="{html_module.escape(field)}" '
        f'data-annotation-severity="{severity}" '
        f'data-annotation-text="{escaped_text}">'
        f'{escaped_value}'
        f'<span class="annotation-marker">&#9873;</span>'
        f'</span>'
    )


def apply_annotations(data: dict, annotations: list[dict] | None) -> dict:
    """Apply annotations to data values by wrapping them in annotation spans.

    Modifies string values in-place where an annotation targets that field.
    Returns the modified data dict.
    """
    if not annotations:
        return data

    annotated = dict(data)
    for ann in annotations:
        field = ann.get("field", "")
        text = ann.get("text", "")
        severity = ann.get("severity", "verify")

        # Handle dotted field paths like "metrics.0.value"
        if field in annotated and isinstance(annotated[field], str):
            annotated[field] = wrap_annotated(annotated[field], field, text, severity)

    return annotated
