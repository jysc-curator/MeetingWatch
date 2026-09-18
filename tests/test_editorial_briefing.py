from scraper.summarize import _material_amounts, _validate_briefing


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


def test_validator_rejects_omitted_material_amounts():
    raw = {
        "overview": "Council will consider utility borrowing.",
        "items": [_item()],
        "routine_items": [],
    }
    _, errors = _validate_briefing(raw, SOURCE)
    assert any("$330,000,000" in error and "$140,000,000" in error for error in errors)


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
