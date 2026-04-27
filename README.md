# bods-xml

Convert [Beneficial Ownership Data Standard (BODS)](https://standard.openownership.org/) v0.4 JSON to XML. Part of the [BODS Interoperability Toolkit](https://github.com/StephenAbbott/bods-interoperability-toolkit).

`bods-xml` ships two output modes:

- **Canonical** — a faithful XML serialisation of BODS 0.4 that preserves every field and mirrors the JSON structure under the namespace `https://standard.openownership.org/ns/0.4`.
- **MRAS preBODS** — the XML format used by Canada's [Multijurisdictional Registry Access Service](https://ised-isde.canada.ca/cbr-rec/en/search) for the BOP2P (Beneficial Ownership Policy to Practice) programme. This restructures BODS's flat statement array into a hierarchical `<preBODS>` document under the namespace `http://mras.ca/schema/preBODS`.

New output profiles (BORIS, XBRL, etc.) can be added as modules under `bods_xml/profiles/`.

## Installation

```bash
pip install -e .
```

For development (includes pytest):

```bash
pip install -e ".[dev]"
```

## CLI usage

```bash
# Canonical BODS XML to stdout
bods-xml input.json

# Canonical BODS XML to file
bods-xml input.json -o output.xml

# MRAS preBODS profile
bods-xml input.json -p mras -o output.xml

# MRAS with explicit timestamp
bods-xml input.json -p mras --timestamp 2024-05-21T14:22:36-04:00 -o output.xml

# JSONL input
bods-xml input.jsonl -p mras -o output.xml
```

## Python API

### Canonical conversion

```python
import json
from bods_xml.canonical import convert, to_string

statements = json.load(open("bods_data.json"))
root = convert(statements)
print(to_string(root))
```

### MRAS preBODS conversion

```python
from bods_xml.profiles.mras import convert, to_string

root = convert(statements, record_timestamp="2024-05-21T14:22:36-04:00")
print(to_string(root))
```

### File-level helpers

Both modules provide `convert_file(path)` which handles JSON and JSONL input:

```python
from bods_xml.canonical import convert_file
root = convert_file("data.jsonl")
```

## Project structure

```
bods-xml/
  src/bods_xml/
    __init__.py
    canonical.py          # Canonical BODS JSON -> XML
    cli.py                # CLI entry point
    profiles/
      __init__.py
      mras.py             # MRAS preBODS output profile
  tests/
    test_canonical.py     # 14 tests
    test_mras_profile.py  # 17 tests
    fixtures/bods_json/   # BODS 0.4 test fixtures
  pyproject.toml
  LICENSE
```

## How the MRAS profile works

The preBODS format restructures BODS's flat array of statements (entity, person, ownershipOrControl) into a hierarchical document:

```xml
<preBODS xmlns="http://mras.ca/schema/preBODS">
  <record_timestamp>2024-05-21T14:22:36-04:00</record_timestamp>
  <entityRecord>           <!-- subject entity -->
    <isSubject>true</isSubject>
    <entityType>registeredEntity</entityType>
    <name>ACME CORP.</name>
    ...
  </entityRecord>
  <relationshipPair>       <!-- one per BO relationship -->
    <personRecord>...</personRecord>
    <relationshipRecord>
      <interests>...</interests>
    </relationshipRecord>
  </relationshipPair>
  <entityRecord>           <!-- linked XP entities -->
    <isSubject>false</isSubject>
    <xpType>XP</xpType>
    ...
  </entityRecord>
</preBODS>
```

Key differences from canonical BODS XML: no statementIds (structure is implicit), bundled `<relationshipPair>` elements, explicit `<beneficialOwnershipOrControl>` boolean, nationality/taxResidency as code+name pairs, and addresses flattened to `<addressLine>`.

## Test fixtures

Five BODS 0.4 JSON fixtures cover the main scenarios from the MRAS sd-exploration files:

| Fixture | Scenario |
|---------|----------|
| `cc_scenario_1.json` | Single person BO (25% shares + board chair) |
| `cc_scenario_2.json` | Two person BOs + linked ON extra-provincial entity |
| `bc_scenario_1.json` | Unknown proximity, date range on interest |
| `qc_scenario_2_entity_bo.json` | Entity as BO (controlByLegalFramework) |
| `qc_scenario_5_exempt.json` | Exempt interest type, indirect proximity |

## Running tests

```bash
pytest
```

## License

MIT
