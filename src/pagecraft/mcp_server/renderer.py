"""Shared HTML rendering logic for MCP tools.

Each tool calls render_component() which loads a Jinja2 template and renders it
with the component's data.
"""
from pathlib import Path

from jinja2 import ChainableUndefined, Environment, FileSystemLoader

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
