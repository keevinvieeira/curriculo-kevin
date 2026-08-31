"""Extracts a normalized, platform-agnostic list of fields from an application form
already loaded in a Playwright page.

Deliberately generic rather than per-ATS: Greenhouse/Lever/Ashby all render standard
HTML form controls with *some* accessible label (a <label for=...>, a wrapping
<label>, an aria-label, or at minimum a placeholder) — reading that generically means
one implementation covers all three ATS and keeps working if any of them tweaks
their markup, instead of three brittle sets of CSS selectors tied to each platform's
current DOM structure.

Radio-button groups (sharing a `name`) collapse into a single FormField with the
group's label taken from a `<fieldset><legend>` or the nearest preceding heading-like
text, and options built from that group's individual radios.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

# Native input types we treat as free-text answers.
_TEXT_INPUT_TYPES = {"text", "email", "tel", "url", "number", "search", ""}
# Types intentionally excluded: they're not questions to answer generically.
_IGNORED_INPUT_TYPES = {"hidden", "submit", "button", "image", "reset"}


@dataclass
class FormField:
    """One question on the application form, ready for answer_engine to resolve."""

    label: str
    field_type: str  # "text" | "textarea" | "select" | "radio" | "checkbox" | "file"
    required: bool = False
    options: List[str] = field(default_factory=list)
    name: str = ""
    locator: Any = None  # Playwright Locator for the element (or radio group name)


def _label_for_element(page, handle) -> str:
    """Best-effort accessible label for a single form element handle."""
    element_id = handle.get_attribute("id")
    if element_id:
        label_el = page.query_selector(f'label[for="{element_id}"]')
        if label_el:
            text = label_el.inner_text().strip()
            if text:
                return text

    aria_label = handle.get_attribute("aria-label")
    if aria_label and aria_label.strip():
        return aria_label.strip()

    labelledby = handle.get_attribute("aria-labelledby")
    if labelledby:
        parts = []
        for ref_id in labelledby.split():
            ref_el = page.query_selector(f'#{ref_id}')
            if ref_el:
                parts.append(ref_el.inner_text().strip())
        text = " ".join(p for p in parts if p)
        if text:
            return text

    # Element wrapped inside a <label>...</label> (no `for`, implicit association).
    wrapping_label = handle.evaluate_handle(
        "el => el.closest('label')"
    )
    try:
        wrapping_el = wrapping_label.as_element()
        if wrapping_el:
            text = wrapping_el.inner_text().strip()
            if text:
                return text
    finally:
        wrapping_label.dispose()

    placeholder = handle.get_attribute("placeholder")
    if placeholder and placeholder.strip():
        return placeholder.strip()

    name = handle.get_attribute("name") or handle.get_attribute("id") or ""
    return name.replace("_", " ").replace("-", " ").strip()


def _is_required(handle) -> bool:
    if handle.get_attribute("required") is not None:
        return True
    aria_required = handle.get_attribute("aria-required")
    if aria_required and aria_required.lower() == "true":
        return True
    return False


def _radio_group_label(page, name: str, first_handle) -> str:
    """Label for a radio group: nearest <fieldset><legend>, else the first radio's
    own accessible label (falls back the same way _label_for_element does)."""
    fieldset = first_handle.evaluate_handle("el => el.closest('fieldset')")
    try:
        fieldset_el = fieldset.as_element()
        if fieldset_el:
            legend = fieldset_el.query_selector("legend")
            if legend:
                text = legend.inner_text().strip()
                if text:
                    return text
    finally:
        fieldset.dispose()
    return _label_for_element(page, first_handle) or name


def extract_form_fields(page) -> List[FormField]:
    """Read every fillable control on `page` into a list of FormField.

    `page` is a Playwright Page (sync API) that has already navigated to the
    application form. Radio buttons sharing a `name` are merged into one FormField;
    everything else maps one-to-one to a FormField.
    """
    fields: List[FormField] = []
    seen_radio_groups: set[str] = set()

    inputs = page.query_selector_all("input")
    for handle in inputs:
        input_type = (handle.get_attribute("type") or "text").lower()
        if input_type in _IGNORED_INPUT_TYPES:
            continue
        if input_type == "checkbox":
            fields.append(
                FormField(
                    label=_label_for_element(page, handle),
                    field_type="checkbox",
                    required=_is_required(handle),
                    name=handle.get_attribute("name") or "",
                    locator=handle,
                )
            )
        elif input_type == "radio":
            name = handle.get_attribute("name") or ""
            if not name or name in seen_radio_groups:
                continue
            seen_radio_groups.add(name)
            group_handles = page.query_selector_all(f'input[type="radio"][name="{name}"]')
            options = []
            for radio_handle in group_handles:
                option_label = _label_for_element(page, radio_handle)
                options.append(option_label or radio_handle.get_attribute("value") or "")
            fields.append(
                FormField(
                    label=_radio_group_label(page, name, handle),
                    field_type="radio",
                    required=_is_required(handle),
                    options=options,
                    name=name,
                    locator=name,  # group identified by name; session.py re-queries per option
                )
            )
        elif input_type == "file":
            fields.append(
                FormField(
                    label=_label_for_element(page, handle),
                    field_type="file",
                    required=_is_required(handle),
                    name=handle.get_attribute("name") or "",
                    locator=handle,
                )
            )
        elif input_type in _TEXT_INPUT_TYPES:
            fields.append(
                FormField(
                    label=_label_for_element(page, handle),
                    field_type="text",
                    required=_is_required(handle),
                    name=handle.get_attribute("name") or "",
                    locator=handle,
                )
            )

    for handle in page.query_selector_all("textarea"):
        fields.append(
            FormField(
                label=_label_for_element(page, handle),
                field_type="textarea",
                required=_is_required(handle),
                name=handle.get_attribute("name") or "",
                locator=handle,
            )
        )

    for handle in page.query_selector_all("select"):
        option_handles = handle.query_selector_all("option")
        options = [opt.inner_text().strip() for opt in option_handles if opt.inner_text().strip()]
        fields.append(
            FormField(
                label=_label_for_element(page, handle),
                field_type="select",
                required=_is_required(handle),
                options=options,
                name=handle.get_attribute("name") or "",
                locator=handle,
            )
        )

    return fields
