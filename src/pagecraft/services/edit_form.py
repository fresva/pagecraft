"""Server-side rendering and parsing for the structured component edit form.

The form lets a researcher/interviewee edit a component's existing field values
in place. It is generated from the component's stored data_json, so every leaf
string becomes an editable input. Adding or removing list items is out of scope
for v1 — apply_edits only writes back to leaves that already exist.
"""
import copy
import html

# Human-readable Swedish labels for known field keys; unknown keys fall back to
# a prettified version of the key itself.
_LABELS = {
    "title": "Titel",
    "description": "Beskrivning",
    "heading": "Rubrik",
    "body_text": "Text",
    "current_situation": "Nuläge",
    "challenge": "Utmaning",
    "solution": "Lösning",
    "label": "Etikett",
    "value": "Värde",
    "municipality": "Kommun",
    "sector": "Sektor",
    "twin_transition": "Twin transition",
    "themes": "Teman",
    "technical_solution": "Teknisk lösning",
    "name": "Namn",
    "organization": "Organisation",
    "email": "E-post",
    "phone": "Telefon",
    "role": "Roll",
    "benefit": "Nytta",
    "quote": "Citat",
    "items": "Nyckeltal",
    "steps": "Steg",
    "personas": "Intressenter",
}

# Fields whose values are usually long enough to warrant a textarea.
_LONG_FIELDS = {
    "description", "body_text", "current_situation", "challenge",
    "solution", "benefit", "quote",
}


def _pretty(key: str) -> str:
    return _LABELS.get(key, key.replace("_", " ").capitalize())


def _field_input(path: str, key: str, value: str) -> str:
    label = _pretty(key)
    safe_val = html.escape(value or "")
    if key in _LONG_FIELDS or len(value or "") > 80:
        control = f'<textarea name="{path}" rows="3">{safe_val}</textarea>'
    else:
        control = f'<input type="text" name="{path}" value="{safe_val}">'
    return f'<label class="edit-field"><span>{html.escape(label)}</span>{control}</label>'


def build_edit_form_html(component_id: int, label: str, data_json: dict) -> str:
    """Render the edit form for a component as HTML (for OOB swap into the modal)."""
    rows: list[str] = []
    for key, value in data_json.items():
        if isinstance(value, str):
            rows.append(_field_input(key, key, value))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    group = [f'<legend>{html.escape(_pretty(key))} {i + 1}</legend>']
                    for subkey, subval in item.items():
                        if isinstance(subval, str):
                            group.append(_field_input(f"{key}.{i}.{subkey}", subkey, subval))
                    rows.append(f'<fieldset class="edit-group">{"".join(group)}</fieldset>')
                elif isinstance(item, str):
                    rows.append(_field_input(f"{key}.{i}", key, item))
        # None / other types are not editable in v1 (e.g. an unset email).

    return (
        f'<div id="edit-modal-content" hx-swap-oob="true">'
        f'<form id="edit-form" data-component-id="{component_id}">'
        f'<h3>Redigera: {html.escape(label)}</h3>'
        f'{"".join(rows)}'
        f'<div class="edit-actions">'
        f'<button type="button" class="btn-save-edit" onclick="saveEdit()">Spara</button>'
        f'<button type="button" class="btn-cancel-edit" onclick="closeEditModal()">Avbryt</button>'
        f'</div>'
        f'</form>'
        f'</div>'
    )


def apply_edits(data_json: dict, fields: dict) -> dict:
    """Return a copy of data_json with submitted values written to existing leaves.

    Only string leaves reachable by an existing dotted path are updated; structure
    (list lengths, dict keys) is never changed. Paths look like "title",
    "items.0.value" or "themes.1".
    """
    edited = copy.deepcopy(data_json)
    for path, value in fields.items():
        parts = path.split(".")
        target = edited
        ok = True
        for part in parts[:-1]:
            if isinstance(target, list) and part.isdigit() and int(part) < len(target):
                target = target[int(part)]
            elif isinstance(target, dict) and part in target:
                target = target[part]
            else:
                ok = False
                break
        if not ok:
            continue
        last = parts[-1]
        if isinstance(target, list):
            if last.isdigit() and int(last) < len(target) and isinstance(target[int(last)], str):
                target[int(last)] = value
        elif isinstance(target, dict):
            if last in target and isinstance(target[last], str):
                target[last] = value
    return edited
