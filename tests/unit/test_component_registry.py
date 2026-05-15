from pagecraft.registry import interview_ordered, load_component_registry


def test_registry_loads_all_components(component_registry):
    assert len(component_registry) == 10


def test_registry_ordered_by_page_order(component_registry):
    orders = [c.page_order for c in component_registry]
    assert orders == sorted(orders)


def test_registry_first_is_hero(component_registry):
    assert component_registry[0].type == "hero"
    assert component_registry[0].label == "Introduktion"


def test_registry_last_is_contact(component_registry):
    assert component_registry[-1].type == "contact"


def test_all_components_have_required_fields(component_registry):
    for comp in component_registry:
        assert comp.type, f"Missing type for component"
        assert comp.label, f"Missing label for {comp.type}"
        assert comp.tool, f"Missing tool for {comp.type}"
        assert comp.template, f"Missing template for {comp.type}"
        assert comp.page_order > 0, f"Invalid page_order for {comp.type}"
        assert comp.interview_order > 0, f"Invalid interview_order for {comp.type}"


def test_component_types_are_unique(component_registry):
    types = [c.type for c in component_registry]
    assert len(types) == len(set(types))


def test_tool_names_follow_convention(component_registry):
    for comp in component_registry:
        assert comp.tool.startswith("write_"), f"Tool {comp.tool} should start with 'write_'"


def test_interview_ordered_returns_conversation_sequence(component_registry):
    ordered = interview_ordered(component_registry)
    assert ordered[0].type == "situation"  # interview_order=1
    assert ordered[-1].type == "contact"   # interview_order=10
    orders = [c.interview_order for c in ordered]
    assert orders == sorted(orders)
