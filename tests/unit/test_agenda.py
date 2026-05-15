"""Tests for InterviewAgenda — section progress tracking."""
from pagecraft.orchestrator.agenda import AgendaItem, InterviewAgenda, SectionStatus
from pagecraft.registry import ComponentDef


def _make_registry(n: int = 3) -> list[ComponentDef]:
    """Create a small registry for testing. interview_order matches page_order for simplicity."""
    return [
        ComponentDef(type=f"comp_{i}", label=f"Label {i}", tool=f"write_comp_{i}",
                      template=f"components/comp_{i}.html", page_order=i, interview_order=i)
        for i in range(1, n + 1)
    ]


def test_initial_state_all_pending():
    agenda = InterviewAgenda(_make_registry())
    for item in agenda.items:
        assert item.status == SectionStatus.PENDING


def test_current_section_returns_first():
    agenda = InterviewAgenda(_make_registry())
    current = agenda.current_section()
    assert current is not None
    assert current.component_type == "comp_1"


def test_update_from_db_marks_agreed():
    agenda = InterviewAgenda(_make_registry())
    agenda.update_from_db({"comp_1": "agreed"})
    assert agenda.items[0].status == SectionStatus.AGREED


def test_update_from_db_marks_draft():
    agenda = InterviewAgenda(_make_registry())
    agenda.update_from_db({"comp_1": "draft"})
    assert agenda.items[0].status == SectionStatus.DRAFT


def test_update_from_db_sets_active_on_first_pending():
    agenda = InterviewAgenda(_make_registry())
    agenda.update_from_db({"comp_1": "agreed"})
    # comp_2 should become ACTIVE (first non-agreed)
    assert agenda.items[1].status == SectionStatus.ACTIVE
    # comp_3 stays PENDING
    assert agenda.items[2].status == SectionStatus.PENDING


def test_current_section_skips_agreed():
    agenda = InterviewAgenda(_make_registry())
    agenda.update_from_db({"comp_1": "agreed", "comp_2": "agreed"})
    current = agenda.current_section()
    assert current is not None
    assert current.component_type == "comp_3"


def test_current_section_returns_none_when_all_agreed():
    agenda = InterviewAgenda(_make_registry())
    agenda.update_from_db({f"comp_{i}": "agreed" for i in range(1, 4)})
    assert agenda.current_section() is None


def test_is_complete_false_when_pending():
    agenda = InterviewAgenda(_make_registry())
    assert agenda.is_complete() is False


def test_is_complete_true_when_all_agreed():
    agenda = InterviewAgenda(_make_registry())
    agenda.update_from_db({f"comp_{i}": "agreed" for i in range(1, 4)})
    assert agenda.is_complete() is True


def test_to_prompt_fragment_format():
    agenda = InterviewAgenda(_make_registry())
    agenda.update_from_db({"comp_1": "agreed", "comp_2": "draft"})
    fragment = agenda.to_prompt_fragment()
    lines = fragment.strip().split("\n")
    assert lines[0] == "[x] Label 1"
    assert lines[1] == "[~] Label 2"
    assert lines[2] == "[>] Label 3"  # first pending becomes ACTIVE


def test_to_prompt_fragment_shows_active():
    agenda = InterviewAgenda(_make_registry())
    agenda.update_from_db({"comp_1": "agreed"})
    fragment = agenda.to_prompt_fragment()
    lines = fragment.strip().split("\n")
    assert lines[1] == "[>] Label 2"


def test_works_with_real_registry(component_registry):
    """Verify agenda works with the real components.yaml registry."""
    agenda = InterviewAgenda(component_registry)
    assert len(agenda.items) == 10
    # Agenda sorts by interview_order, so first item is situation (interview_order=1)
    assert agenda.items[0].component_type == "situation"
    assert agenda.current_section().component_type == "situation"
