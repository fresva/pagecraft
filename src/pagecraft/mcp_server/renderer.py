"""Shared HTML rendering logic for MCP tools.

Each tool calls render_component() which loads a Jinja2 template
and embeds annotations as data attributes.
"""
import html as html_module
from pathlib import Path

from jinja2 import ChainableUndefined, Environment, FileSystemLoader
from markupsafe import Markup

_templates_dir = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(_templates_dir),
    undefined=ChainableUndefined,
    autoescape=True,
)


def render_component(template_name: str, data: dict) -> str:
    """Render a component template with the given data."""
    template = _jinja_env.get_template(template_name)
    return template.render(**data)


def wrap_annotated(value: str, field: str, text: str, severity: str) -> Markup:
    """Wrap a value in an annotation span with data attributes.

    Returns the value wrapped in a <span> with annotation metadata,
    flagged as Markup so the Jinja2 autoescape leaves it intact when the
    template renders the annotated field.
    """
    severity_class = f"annotation-{severity}"
    escaped_text = html_module.escape(text)
    escaped_value = html_module.escape(str(value))
    return Markup(
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

    Only matches top-level string fields. Nested paths (e.g. items.0.value)
    are not supported yet and will be added when Phase 3 needs them.
    """
    if not annotations:
        return data

    annotated = dict(data)
    for ann in annotations:
        field = ann.get("field", "")
        text = ann.get("text", "")
        severity = ann.get("severity", "verify")

        if field in annotated and isinstance(annotated[field], str):
            annotated[field] = wrap_annotated(annotated[field], field, text, severity)

    return annotated
