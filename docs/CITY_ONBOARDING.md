# City Onboarding (Config-First)

Issue: #5 (Self-serve city onboarding)

## Goal
Add new cities through configuration for supported platform templates without immediate scraper code edits.

## Supported templates
- `agendasuite`
- `civicclerk`

## Config file
Start from:
- `config/cities.example.json`

Required fields per city:
- `city` (string)
- `platform` (`agendasuite|civicclerk`)
- `timezone` (must be `America/*`)
- `source_url` (http/https URL)
- `parser_template` (`agendasuite|civicclerk`)
- `enabled` (boolean)

Approval-gate field:
- `approval_ticket` (required when `enabled=true`)

## Validation
```bash
python scripts/onboarding_validate.py --config config/cities.example.json
```

## Dry-run (non-production)
```bash
python scripts/onboarding_validate.py --config config/cities.example.json --dry-run
```

Dry-run only verifies source URL reachability/content type. It does not modify production data.

## Production enable flow
1. Add city config with `enabled: false`
2. Run validator + dry-run and collect output
3. Obtain explicit approval ticket (e.g. `APPROVE: city-<name>`)
4. Set `enabled: true` and include `approval_ticket`
5. Merge + monitor next scheduled run

## Rollback
If a city causes bad output:
1. Set `enabled: false`
2. Re-run validator to confirm config integrity
3. Merge rollback and monitor next run
