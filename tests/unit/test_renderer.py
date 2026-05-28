"""Tests for Jinja2 component template rendering."""
from pathlib import Path

import pytest


def test_all_component_templates_exist(component_registry):
    templates_dir = Path(__file__).parent.parent.parent / "src" / "pagecraft" / "templates"
    for comp in component_registry:
        template_path = templates_dir / comp.template
        assert template_path.exists(), f"Template missing: {comp.template}"


# --- Hero ---

def test_hero_renders_with_defaults(jinja_env):
    template = jinja_env.get_template("components/hero.html")
    html = template.render()
    assert "Projekttitel" in html
    assert "<h1" in html


def test_hero_renders_with_custom_data(jinja_env):
    template = jinja_env.get_template("components/hero.html")
    html = template.render(title="Test Title", description="Custom desc")
    assert "Test Title" in html
    assert "Custom desc" in html
    assert "Projekttitel" not in html


# --- Metadata ---

def test_metadata_renders_defaults(jinja_env):
    template = jinja_env.get_template("components/metadata.html")
    html = template.render()
    assert "metadata-bar" in html
    assert "Kommun" in html
    assert "Sektor" in html
    assert "metadata-tag" in html


def test_metadata_renders_custom_tags(jinja_env):
    template = jinja_env.get_template("components/metadata.html")
    html = template.render(
        municipality="Göteborg",
        sector="Transport",
        themes=["Energi", "Mobilitet"],
        technical_solution=["IoT"],
    )
    assert "Göteborg" in html
    assert "Transport" in html
    assert "Energi" in html
    assert "Mobilitet" in html
    assert "IoT" in html


# --- Situation ---

def test_situation_renders_three_columns(jinja_env):
    template = jinja_env.get_template("components/situation.html")
    html = template.render()
    assert html.count("situation-column") == 3
    assert "Nuläge" in html
    assert "Utmaning" in html
    assert "Lösning" in html


def test_situation_renders_custom_data(jinja_env):
    template = jinja_env.get_template("components/situation.html")
    html = template.render(
        current_situation="Current state",
        challenge="Big challenge",
        solution="Smart solution",
    )
    assert "Current state" in html
    assert "Big challenge" in html
    assert "Smart solution" in html


# --- KPIs ---

def test_kpis_empty_renders_no_cells(jinja_env):
    template = jinja_env.get_template("components/kpis.html")
    html = template.render()
    assert html.count("kpi-cell") == 0


def test_kpis_renders_variable_count(jinja_env):
    template = jinja_env.get_template("components/kpis.html")
    html = template.render(items=[
        {"label": "CO2", "value": "-30%", "description": "Minskade utsläpp"},
        {"label": "ROI", "value": "2x", "description": "Avkastning"},
    ])
    assert html.count("kpi-cell") == 2
    assert "-30%" in html
    assert "Minskade utsläpp" in html
    assert "2x" in html


# --- Impact ---

def test_impact_empty_renders_no_cards(jinja_env):
    template = jinja_env.get_template("components/impact.html")
    html = template.render()
    assert html.count("impact-card") == 0


def test_impact_renders_variable_count(jinja_env):
    template = jinja_env.get_template("components/impact.html")
    html = template.render(items=[
        {"label": "CO2", "value": ">50%", "description": "Stor minskning"},
    ])
    assert html.count("impact-card") == 1
    # autoescape turns the literal ">" into "&gt;"
    assert "&gt;50%" in html


# --- Implementation ---

def test_implementation_renders_narrative(jinja_env):
    template = jinja_env.get_template("components/implementation.html")
    html = template.render()
    assert "Implementeringsberättelse" in html
    assert "implementation-body" in html


def test_implementation_renders_custom_data(jinja_env):
    template = jinja_env.get_template("components/implementation.html")
    html = template.render(heading="Vår resa", body_text="Det började med...")
    assert "Vår resa" in html
    assert "Det började med..." in html


# --- Resources ---

def test_resources_renders_defaults(jinja_env):
    template = jinja_env.get_template("components/resources.html")
    html = template.render()
    assert "Resurser" in html
    assert "component-resources" in html


def test_resources_renders_custom_data(jinja_env):
    template = jinja_env.get_template("components/resources.html")
    html = template.render(heading="Verktyg", body_text="Vi använde X och Y.")
    assert "Verktyg" in html
    assert "Vi använde X och Y." in html


# --- Getting Started ---

def test_getting_started_empty_renders_no_steps(jinja_env):
    template = jinja_env.get_template("components/getting_started.html")
    html = template.render()
    assert html.count("step-card") == 0


def test_getting_started_numbers_from_position(jinja_env):
    template = jinja_env.get_template("components/getting_started.html")
    html = template.render(steps=[
        {"title": "Först", "description": "A"},
        {"title": "Sen", "description": "B"},
        {"title": "Sist", "description": "C"},
    ])
    assert html.count("step-card") == 3
    assert ">1<" in html and ">2<" in html and ">3<" in html


# --- Personas ---

def test_personas_empty_renders_no_cards(jinja_env):
    template = jinja_env.get_template("components/personas.html")
    html = template.render()
    assert html.count("persona-card") == 0


def test_personas_renders_variable_count(jinja_env):
    template = jinja_env.get_template("components/personas.html")
    html = template.render(personas=[
        {"role": "Planerare", "benefit": "Bättre underlag", "quote": "Toppen"},
        {"role": "Politiker", "benefit": "Tydligare beslut"},
    ])
    assert html.count("persona-card") == 2
    assert "Planerare" in html
    assert "Toppen" in html


# --- Contact ---

def test_contact_renders_defaults(jinja_env):
    template = jinja_env.get_template("components/contact.html")
    html = template.render()
    assert "[Namn]" in html
    assert "[Titel]" in html
    assert "[Organisation]" in html


# --- Cross-cutting ---

def test_all_templates_render_without_errors(jinja_env, component_registry):
    """Every component template should render with no context (using defaults)."""
    for comp in component_registry:
        template = jinja_env.get_template(comp.template)
        html = template.render()
        assert len(html) > 50, f"Template {comp.template} rendered too little content"
