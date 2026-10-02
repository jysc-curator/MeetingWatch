import scraper.summarize as summarizer
from scraper.summarize import (
    _coverage_warnings,
    _material_amounts,
    _response_schema,
    _validate_briefing,
)


SOURCE = """[PAGE 6]
8.A. Ordinance 26-49 authorizes Utilities System Refunding Revenue Bonds in an
aggregate principal amount not to exceed $225,000,000.
8.B. Ordinance 26-50 authorizes $330,000,000 in tax-exempt bonds and
$140,000,000 in taxable bonds.

[PAGE 7]
9.A. A public hearing will consider rezoning 14.09 acres from CR to RM-30.
"""


def _item(**overrides):
    item = {
        "headline": "Council weighs $225 million utility bond",
        "action": "Council will consider Ordinance 26-49 authorizing up to $225,000,000 in utility refunding bonds.",
        "why_it_matters": "The proposal would authorize major utility borrowing.",
        "priority": "top",
        "category": "money",
        "agenda_item": "8.A",
        "source_page": 99,
        "key_facts": ["Up to $225,000,000"],
        "evidence": "aggregate principal amount not to exceed $225,000,000",
    }
    item.update(overrides)
    return item


def test_validator_accepts_semantically_equivalent_money_and_corrects_page():
    raw = {
        "overview": "Council will consider three utility bond authorizations.",
        "items": [
            _item(),
            _item(
                headline="New utility bonds include $330 million and $140 million",
                action="Ordinance 26-50 would authorize $330,000,000 tax-exempt and $140,000,000 taxable bonds.",
                agenda_item="8.B",
                key_facts=["$330,000,000 tax-exempt", "$140,000,000 taxable"],
                evidence="Ordinance 26-50 authorizes $330,000,000 in tax-exempt bonds and $140,000,000 in taxable bonds",
            ),
        ],
        "routine_items": [],
    }
    briefing, errors = _validate_briefing(raw, SOURCE)
    assert errors == []
    assert briefing["items"][0]["source_page"] == 6


def test_validator_rejects_unverifiable_evidence_and_numbers():
    raw = {
        "overview": "Council will vote.",
        "items": [
            _item(
                action="Council approved a $999,000,000 bond.",
                evidence="Council approved the bond unanimously",
            )
        ],
        "routine_items": [],
    }
    _, errors = _validate_briefing(raw, SOURCE)
    assert errors
    assert any("unsupported numeric facts" in error or "could not anchor" in error for error in errors)


def test_validator_does_not_require_unselected_agenda_amounts():
    raw = {
        "overview": "Council will consider utility borrowing.",
        "items": [_item()],
        "routine_items": [],
    }
    _, errors = _validate_briefing(raw, SOURCE)
    assert errors == []


def test_unselected_major_amounts_are_coverage_warnings_not_safety_failures():
    raw = {
        "overview": "Council will consider utility borrowing.",
        "items": [_item()],
        "routine_items": [],
    }
    briefing, errors = _validate_briefing(raw, SOURCE)
    assert errors == []
    warnings = _coverage_warnings(briefing, SOURCE)
    assert len(warnings) == 1
    assert "$330,000,000" in warnings[0]
    assert "$140,000,000" in warnings[0]


def test_validator_rejects_amount_omitted_from_selected_item():
    raw = {
        "overview": "Council will consider utility borrowing.",
        "items": [
            _item(
                headline="Utility refunding bond proposal",
                action="Council will consider the utility refunding bond proposal.",
                why_it_matters="The proposal would authorize major utility borrowing.",
                key_facts=[],
            )
        ],
        "routine_items": [],
    }
    _, errors = _validate_briefing(raw, SOURCE)
    assert any("material amounts omitted" in error and "$225,000,000" in error for error in errors)


def test_material_amounts_are_ranked_and_deduplicated():
    assert _material_amounts(SOURCE)[:3] == ["$330,000,000", "$225,000,000", "$140,000,000"]


def test_validator_tolerates_pdf_typography_variants_in_verbatim_evidence():
    raw = {
        "overview": "Council will consider utility borrowing.",
        "items": [
            _item(),
            _item(
                headline="New utility bonds include $330 million and $140 million",
                action="Ordinance 26-50 would authorize $330,000,000 tax-exempt and $140,000,000 taxable bonds.",
                agenda_item="8.B",
                key_facts=["$330,000,000 tax-exempt", "$140,000,000 taxable"],
                evidence="Ordinance 26‑50 authorizes $330,000,000 in tax‑exempt bonds and $140,000,000 in taxable bonds",
            ),
        ],
        "routine_items": [],
    }
    briefing, errors = _validate_briefing(raw, SOURCE)
    assert errors == []
    assert briefing["items"][1]["source_page"] == 6


def test_validator_recovers_a_verbatim_source_block_from_paraphrased_evidence():
    raw = {
        "overview": "Council will consider three utility bond authorizations.",
        "items": [
            _item(evidence="A paraphrase that does not appear exactly in the agenda."),
            _item(
                headline="New utility bonds include $330 million and $140 million",
                action="Ordinance 26-50 would authorize $330,000,000 tax-exempt and $140,000,000 taxable bonds.",
                agenda_item="8.B",
                key_facts=["$330,000,000 tax-exempt", "$140,000,000 taxable"],
                evidence="The city may issue two improvement bond series.",
            ),
        ],
        "routine_items": [],
    }
    briefing, errors = _validate_briefing(raw, SOURCE)
    assert errors == []
    assert "aggregate principal amount not to exceed $225,000,000" in briefing["items"][0]["evidence"]
    assert briefing["items"][1]["source_page"] == 6


def test_numeric_validation_handles_pdf_line_wrapping():
    source = "[PAGE 1]\nA request to rezone 14.09\nacres from CR to RM-30."
    raw = {
        "overview": "Commissioners will consider a rezoning.",
        "items": [
            {
                "headline": "Rezone 14.09 acres",
                "action": "Commissioners will consider rezoning 14.09 acres from CR to RM-30.",
                "why_it_matters": "The action would change the permitted land use.",
                "priority": "top",
                "category": "land-use",
                "agenda_item": None,
                "source_page": 1,
                "key_facts": ["14.09 acres"],
                "evidence": "A request to rezone 14.09 acres from CR to RM-30.",
            }
        ],
        "routine_items": [],
    }
    _, errors = _validate_briefing(raw, source)
    assert errors == []


def test_numeric_validation_handles_hyphenated_singular_acreage():
    source = "[PAGE 1]\nA request to rezone one 47.55-acre property from RR-5 to RR-2.5."
    raw = {
        "overview": "Commissioners will consider a rezoning.",
        "items": [
            {
                "headline": "Rezone a 47.55-acre property",
                "action": "Commissioners will consider rezoning 47.55 acres from RR-5 to RR-2.5.",
                "why_it_matters": "The action would change the permitted residential density.",
                "priority": "top",
                "category": "land-use",
                "agenda_item": "P-26-008",
                "source_page": 1,
                "key_facts": ["47.55 acres", "RR-5 to RR-2.5"],
                "evidence": "A request to rezone one 47.55-acre property from RR-5 to RR-2.5.",
            }
        ],
        "routine_items": [],
    }
    _, errors = _validate_briefing(raw, source)
    assert errors == []


def test_validator_recovers_evidence_from_plain_text_without_pages():
    source = """[SOURCE TEXT]
M8   A Resolution establishing Project CI2621 – Aviation Asset Defense and approving a
     transfer of $300,000 from Project CIAN18 – Grant Matches Airport

N7   An Ordinance transferring $600,000 for demolition of unsafe structures
"""
    raw = {
        "overview": "Council will consider an airport project transfer.",
        "items": [
            {
                "headline": "$300,000 transfer for Aviation Asset Defense",
                "action": "Council will consider transferring $300,000 to establish the Aviation Asset Defense project.",
                "why_it_matters": "The proposal would move airport grant-match money into a new project.",
                "priority": "top",
                "category": "money",
                "agenda_item": "M8",
                "source_page": None,
                "key_facts": ["$300,000 transfer"],
                "evidence": "The agenda proposes an airport project transfer.",
            }
        ],
        "routine_items": [],
    }
    briefing, errors = _validate_briefing(raw, source)
    assert errors == []
    assert briefing["items"][0]["evidence"].startswith("M8 A Resolution")
    assert briefing["items"][0]["source_page"] is None


def test_summarizer_publishes_valid_subset_when_another_story_fails(monkeypatch, tmp_path):
    source = """[SOURCE TEXT]
M8   A Resolution establishing Project CI2621 – Aviation Asset Defense and approving a transfer of $300,000 from Project CIAN18 – Grant Matches Airport

N7   An Ordinance transferring funds in the amount of $600,000.00 for demolition of unsafe structures

N11  An Ordinance transferring $400,000 from the Airport Fund to Project CI2621 – Aviation Asset Defense
"""
    valid = {
        "headline": "$300,000 transfer for Aviation Asset Defense",
        "action": "Council will consider a $300,000 transfer to establish Project CI2621.",
        "why_it_matters": "The proposal would redirect airport grant-match funds.",
        "priority": "top",
        "category": "money",
        "agenda_item": "M8",
        "source_page": None,
        "key_facts": ["$300,000", "Project CI2621"],
        "evidence": "M8   A Resolution establishing Project CI2621 – Aviation Asset Defense and approving a transfer of $300,000 from Project CIAN18 – Grant Matches Airport",
    }
    combined = {
        "headline": "Three transfers totaling $1,300,000",
        "action": "Council will consider three transfers totaling $1,300,000.",
        "why_it_matters": "The actions would fund airport defense and demolition.",
        "priority": "top",
        "category": "money",
        "agenda_item": "M8, N7, N11",
        "source_page": None,
        "key_facts": ["$1,300,000"],
        "evidence": "Three related transfers are proposed.",
    }
    raw = {
        "overview": "Council will consider three transfers totaling $1,300,000.",
        "items": [valid, combined],
        "routine_items": [],
    }
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(summarizer, "_fetch_text_url", lambda _url: (source, ""))
    monkeypatch.setattr(summarizer, "_call_openai", lambda *_args, **_kwargs: (raw, "test"))

    result = summarizer.summarize_meeting(
        {"agenda_text_url": "https://example.test/agenda.txt"},
        cache_dir=tmp_path,
    )

    assert result.ok is True
    assert result.status == "verified"
    assert len(result.briefing["items"]) == 1
    assert result.briefing["items"][0]["agenda_item"] == "M8"
    assert "$1,300,000" not in result.briefing["overview"]
    assert "discarded draft content" in result.reason


def test_summarizer_retries_to_restore_major_amount_coverage(monkeypatch, tmp_path):
    first_draft = {
        "overview": "Council will consider utility borrowing.",
        "items": [_item()],
        "routine_items": [],
    }
    complete_draft = {
        "overview": "Council will consider three utility bond authorizations.",
        "items": [
            _item(),
            _item(
                headline="New utility bonds include $330 million and $140 million",
                action="Ordinance 26-50 would authorize $330,000,000 tax-exempt and $140,000,000 taxable bonds.",
                agenda_item="8.B",
                key_facts=["$330,000,000 tax-exempt", "$140,000,000 taxable"],
                evidence="Ordinance 26-50 authorizes $330,000,000 in tax-exempt bonds and $140,000,000 in taxable bonds",
            ),
        ],
        "routine_items": [],
    }
    drafts = iter([first_draft, complete_draft])
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(summarizer, "_fetch_text_url", lambda _url: (SOURCE, ""))
    monkeypatch.setattr(
        summarizer,
        "_call_openai",
        lambda *_args, **_kwargs: (next(drafts), "test"),
    )

    result = summarizer.summarize_meeting(
        {"agenda_text_url": "https://example.test/agenda.txt"},
        cache_dir=tmp_path,
    )

    assert result.ok is True
    assert result.attempts == 2
    assert result.reason == ""
    assert len(result.briefing["items"]) == 2


def test_retry_requires_an_item_when_a_high_signal_agenda_first_returns_empty(
    monkeypatch, tmp_path
):
    source = """[SOURCE TEXT]
Unfinished Business / Action Items

12. Ordinance 2026-24 amending the municipal code to authorize two alternate
    members of the Historic Preservation Commission. Second reading and public hearing

New Business / Action Items

18. Resolution 2026-30 approving a memorandum of understanding regarding
    regional affordable housing collaboration
"""
    empty_draft = {
        "overview": "No consequential items were identified.",
        "items": [],
        "routine_items": [],
    }
    valid_draft = {
        "overview": "Council will consider a municipal-code amendment.",
        "items": [
            {
                "headline": "Historic Preservation Commission alternates",
                "action": "Council will consider Ordinance 2026-24 authorizing two alternate commission members.",
                "why_it_matters": "The proposal would change the commission's authorized membership.",
                "priority": "top",
                "category": "governance",
                "agenda_item": "12",
                "source_page": None,
                "key_facts": ["Second reading and public hearing", "Two alternate members"],
                "evidence": "12. Ordinance 2026-24 amending the municipal code to authorize two alternate members of the Historic Preservation Commission. Second reading and public hearing",
            }
        ],
        "routine_items": [],
    }
    drafts = iter([empty_draft, valid_draft])
    require_item_values = []

    def fake_call(_source, _model, _correction="", require_item=False):
        require_item_values.append(require_item)
        return next(drafts), "test"

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(summarizer, "_fetch_text_url", lambda _url: (source, ""))
    monkeypatch.setattr(summarizer, "_call_openai", fake_call)

    result = summarizer.summarize_meeting(
        {"agenda_text_url": "https://example.test/salida-agenda.txt"},
        cache_dir=tmp_path,
    )

    assert require_item_values == [False, True]
    assert result.ok is True
    assert result.status == "verified"
    assert result.attempts == 2
    assert result.briefing["items"][0]["agenda_item"] == "12"


def test_response_schema_only_requires_items_for_high_signal_recovery():
    assert "minItems" not in _response_schema()["schema"]["properties"]["items"]
    assert _response_schema(require_item=True)["schema"]["properties"]["items"]["minItems"] == 1
