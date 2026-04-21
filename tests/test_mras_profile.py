"""Tests for MRAS preBODS output profile."""

import json
from pathlib import Path

import pytest
from lxml import etree

from bods_xml.profiles.mras import convert, convert_file, to_string, PREBODS_NS

FIXTURES = Path(__file__).parent / "fixtures" / "bods_json"
NS = {"p": PREBODS_NS}

FIXED_TIMESTAMP = "2024-05-21T14:22:36.971843-04:00"


def _load(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text())


class TestMrasPreBodsStructure:
    """Test the preBODS XML structure matches the sd-exploration pattern."""

    def test_root_element_is_prebods(self):
        stmts = _load("cc_scenario_1.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        assert root.tag == f"{{{PREBODS_NS}}}preBODS"

    def test_record_timestamp(self):
        stmts = _load("cc_scenario_1.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        ts = root.findtext("p:record_timestamp", namespaces=NS)
        assert ts == FIXED_TIMESTAMP

    def test_subject_entity_first(self):
        stmts = _load("cc_scenario_1.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        children = list(root)
        # First child is record_timestamp, second is entityRecord
        assert children[1].tag == f"{{{PREBODS_NS}}}entityRecord"
        assert children[1].findtext("p:isSubject", namespaces=NS) == "true"

    def test_subject_entity_fields(self):
        stmts = _load("cc_scenario_1.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        entity = root.find("p:entityRecord", NS)
        assert entity.findtext("p:entityType", namespaces=NS) == "registeredEntity"
        assert entity.findtext("p:name", namespaces=NS) == "12345678 CANADA CORP."
        assert entity.findtext("p:foundingDate", namespaces=NS) == "2021-05-11"

        ids = entity.findall(".//p:identifier", NS)
        assert len(ids) == 2
        schemes = [i.findtext("p:scheme", namespaces=NS) for i in ids]
        assert "CA-BN" in schemes
        assert "CA-CC" in schemes

    def test_relationship_pair_structure(self):
        stmts = _load("cc_scenario_1.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        pairs = root.findall("p:relationshipPair", NS)
        assert len(pairs) == 1

        pair = pairs[0]
        person = pair.find("p:personRecord", NS)
        rel = pair.find("p:relationshipRecord", NS)
        assert person is not None
        assert rel is not None

    def test_person_record_fields(self):
        stmts = _load("cc_scenario_1.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        pair = root.find("p:relationshipPair", NS)
        person = pair.find("p:personRecord", NS)

        assert person.findtext("p:personType", namespaces=NS) == "knownPerson"
        assert person.findtext("p:birthDate", namespaces=NS) == "2001-01-01"

        names = person.find("p:names", NS)
        assert names.findtext("p:type", namespaces=NS) == "individual"
        assert names.findtext("p:fullName", namespaces=NS) == "Bob Orino"
        assert names.findtext("p:givenName", namespaces=NS) == "Bob"
        assert names.findtext("p:familyName", namespaces=NS) == "Orino"

    def test_relationship_record_interests(self):
        stmts = _load("cc_scenario_1.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        pair = root.find("p:relationshipPair", NS)
        rel = pair.find("p:relationshipRecord", NS)

        interests = rel.findall(".//p:interest", NS)
        assert len(interests) == 2

        # Share
        share_int = interests[0]
        assert share_int.findtext("p:type", namespaces=NS) == "share"
        assert share_int.findtext("p:directOrIndirect", namespaces=NS) == "direct"
        assert share_int.findtext("p:beneficialOwnershipOrControl", namespaces=NS) == "true"
        assert share_int.findtext(".//p:exact", namespaces=NS) == "25"

        # Board chair
        board_int = interests[1]
        assert board_int.findtext("p:type", namespaces=NS) == "boardChair"
        assert board_int.findtext("p:details", namespaces=NS) == "Chair of the board. Calls the shots."
        assert board_int.findtext("p:startDate", namespaces=NS) == "2022-01-01"


class TestMrasMultipleBOs:
    """Test scenarios with multiple beneficial owners."""

    def test_two_person_bos(self):
        stmts = _load("cc_scenario_2.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        pairs = root.findall("p:relationshipPair", NS)
        assert len(pairs) == 2

        # Each pair should have a personRecord
        for pair in pairs:
            assert pair.find("p:personRecord", NS) is not None
            assert pair.find("p:relationshipRecord", NS) is not None

    def test_linked_entity_not_in_pairs(self):
        """Non-subject, non-IP entities should appear as standalone entityRecords."""
        stmts = _load("cc_scenario_2.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        entity_records = root.findall("p:entityRecord", NS)

        # Should have subject entity + linked ON XP entity
        assert len(entity_records) == 2
        subjects = [e for e in entity_records
                    if e.findtext("p:isSubject", namespaces=NS) == "true"]
        non_subjects = [e for e in entity_records
                       if e.findtext("p:isSubject", namespaces=NS) == "false"]
        assert len(subjects) == 1
        assert len(non_subjects) == 1
        assert non_subjects[0].findtext("p:name", namespaces=NS) == "BLAZING GLAZING CERAMICS ON XP"

    def test_tax_residencies_in_person(self):
        stmts = _load("cc_scenario_2.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        pairs = root.findall("p:relationshipPair", NS)

        # Second person (Reginald) has taxResidencies
        person2 = pairs[1].find("p:personRecord", NS)
        tr = person2.findall(".//p:taxResidency", NS)
        assert len(tr) == 1
        assert tr[0].findtext("p:code", namespaces=NS) == "CA"


class TestMrasEntityBOs:
    """Test entity-as-beneficial-owner scenarios."""

    def test_entity_in_relationship_pair(self):
        stmts = _load("qc_scenario_2_entity_bo.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        pairs = root.findall("p:relationshipPair", NS)
        assert len(pairs) == 1

        pair = pairs[0]
        # Should have entityRecord (not personRecord) in pair
        entity_in_pair = pair.find("p:entityRecord", NS)
        assert entity_in_pair is not None
        assert entity_in_pair.findtext("p:name", namespaces=NS) == "Valcour SHELL CORP."
        assert entity_in_pair.findtext("p:isSubject", namespaces=NS) == "false"

        person_in_pair = pair.find("p:personRecord", NS)
        assert person_in_pair is None

    def test_control_by_legal_framework_interest(self):
        stmts = _load("qc_scenario_2_entity_bo.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        pair = root.find("p:relationshipPair", NS)
        rel = pair.find("p:relationshipRecord", NS)
        interest = rel.find(".//p:interest", NS)
        assert interest.findtext("p:type", namespaces=NS) == "controlByLegalFramework"
        assert interest.findtext("p:directOrIndirect", namespaces=NS) == "direct"
        assert interest.findtext("p:startDate", namespaces=NS) == "2023-06-01"

    def test_exempt_indirect(self):
        stmts = _load("qc_scenario_5_exempt.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        pair = root.find("p:relationshipPair", NS)
        rel = pair.find("p:relationshipRecord", NS)
        interest = rel.find(".//p:interest", NS)
        assert interest.findtext("p:type", namespaces=NS) == "exempt"
        assert interest.findtext("p:directOrIndirect", namespaces=NS) == "indirect"


class TestMrasEdgeCases:
    """Test edge cases: unknown proximity, missing fields, date ranges."""

    def test_unknown_proximity(self):
        stmts = _load("bc_scenario_1.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        pair = root.find("p:relationshipPair", NS)
        rel = pair.find("p:relationshipRecord", NS)
        interest = rel.find(".//p:interest", NS)
        assert interest.findtext("p:directOrIndirect", namespaces=NS) == "unknown"

    def test_interest_date_range(self):
        stmts = _load("bc_scenario_1.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        pair = root.find("p:relationshipPair", NS)
        rel = pair.find("p:relationshipRecord", NS)
        interest = rel.find(".//p:interest", NS)
        assert interest.findtext("p:startDate", namespaces=NS) == "2011-09-09"
        assert interest.findtext("p:endDate", namespaces=NS) == "2021-05-19"

    def test_nationalities_as_code_name_pairs(self):
        stmts = _load("bc_scenario_1.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        pair = root.find("p:relationshipPair", NS)
        person = pair.find("p:personRecord", NS)
        nats = person.findall(".//p:nationality", NS)
        assert len(nats) == 2
        codes = [n.findtext("p:code", namespaces=NS) for n in nats]
        assert "CA" in codes
        assert "BE" in codes

    def test_xml_well_formed(self):
        stmts = _load("cc_scenario_2.json")
        root = convert(stmts, record_timestamp=FIXED_TIMESTAMP)
        xml_str = to_string(root)
        assert xml_str.startswith("<?xml")
        parsed = etree.fromstring(xml_str.encode("utf-8"))
        assert parsed.tag == f"{{{PREBODS_NS}}}preBODS"
