"""Tests for engine/application/form_parser.py — driven against a real headless
Chromium page (via page.set_content), not a mock. Chromium ships pre-installed in
this dev sandbox; the fixture HTML below never makes a network request."""
from __future__ import annotations

from engine.application.form_parser import extract_form_fields

_FIXTURE_HTML = """
<html><body>
<form>
  <label for="full_name">Full Name *</label>
  <input type="text" id="full_name" name="full_name" required>

  <label for="email_addr">Email</label>
  <input type="email" id="email_addr" name="email">

  <label>
    Cover Letter
    <textarea name="cover_letter"></textarea>
  </label>

  <label for="country">Country</label>
  <select id="country" name="country">
    <option value="">Select...</option>
    <option value="br">Brazil</option>
    <option value="us">United States</option>
  </select>

  <fieldset>
    <legend>Are you legally authorized to work in Brazil?</legend>
    <input type="radio" name="work_auth" value="yes" id="wa_yes">
    <label for="wa_yes">Yes</label>
    <input type="radio" name="work_auth" value="no" id="wa_no">
    <label for="wa_no">No</label>
  </fieldset>

  <input type="checkbox" name="consent" id="consent" required>
  <label for="consent">I agree to the privacy policy *</label>

  <input type="file" name="resume" id="resume_upload">
  <label for="resume_upload">Resume/CV</label>

  <input type="hidden" name="csrf_token" value="abc123">
  <button type="submit">Submit Application</button>
</form>
</body></html>
"""


def test_extracts_text_field_with_label_and_required(playwright_page):
    playwright_page.set_content(_FIXTURE_HTML)
    fields = extract_form_fields(playwright_page)

    name_field = next(f for f in fields if f.name == "full_name")
    assert name_field.field_type == "text"
    assert name_field.required is True
    assert "Full Name" in name_field.label


def test_extracts_email_field_without_required(playwright_page):
    playwright_page.set_content(_FIXTURE_HTML)
    fields = extract_form_fields(playwright_page)

    email_field = next(f for f in fields if f.name == "email_addr" or f.name == "email")
    assert email_field.field_type == "text"
    assert email_field.required is False


def test_extracts_textarea_wrapped_in_implicit_label(playwright_page):
    playwright_page.set_content(_FIXTURE_HTML)
    fields = extract_form_fields(playwright_page)

    cover_letter_field = next(f for f in fields if f.name == "cover_letter")
    assert cover_letter_field.field_type == "textarea"
    assert "Cover Letter" in cover_letter_field.label


def test_extracts_select_field_with_options(playwright_page):
    playwright_page.set_content(_FIXTURE_HTML)
    fields = extract_form_fields(playwright_page)

    country_field = next(f for f in fields if f.name == "country")
    assert country_field.field_type == "select"
    assert "Brazil" in country_field.options
    assert "United States" in country_field.options


def test_merges_radio_group_into_single_field_with_options(playwright_page):
    playwright_page.set_content(_FIXTURE_HTML)
    fields = extract_form_fields(playwright_page)

    radio_fields = [f for f in fields if f.field_type == "radio"]
    assert len(radio_fields) == 1
    work_auth_field = radio_fields[0]
    assert "legally authorized" in work_auth_field.label.casefold()
    assert set(work_auth_field.options) == {"Yes", "No"}


def test_extracts_checkbox_as_required(playwright_page):
    playwright_page.set_content(_FIXTURE_HTML)
    fields = extract_form_fields(playwright_page)

    checkbox_field = next(f for f in fields if f.field_type == "checkbox")
    assert checkbox_field.required is True
    assert "privacy policy" in checkbox_field.label.casefold()


def test_extracts_file_field(playwright_page):
    playwright_page.set_content(_FIXTURE_HTML)
    fields = extract_form_fields(playwright_page)

    file_field = next(f for f in fields if f.field_type == "file")
    assert "resume" in file_field.label.casefold() or "cv" in file_field.label.casefold()


def test_ignores_hidden_and_submit_inputs(playwright_page):
    playwright_page.set_content(_FIXTURE_HTML)
    fields = extract_form_fields(playwright_page)

    names = [f.name for f in fields]
    assert "csrf_token" not in names
    assert not any(f.field_type not in ("text", "textarea", "select", "radio", "checkbox", "file") for f in fields)
