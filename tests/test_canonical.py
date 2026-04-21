"""Tests for canonical BODS JSON -> XML conversion."""

import json
from pathlib import Path

import pytest
from lxml import etree

from bods_xml.canonical import convert, convert_file, to_string, BODS_NS

FIXTURES = Path(__file__).parent / "fixtures" / "bods_json"
NS = {"b": BODS_NS}


def _load(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text())


class TestCanonicalConvert:
    """Test canonical XML output structure."""

    def test_root_element_is_bods_dataset(self):
        stmts = _load("cc_scenario_1.json")
        root = convert(stmts)
        assert root.tag == f"{{{BODS_NS}}}bodsDataset"

    def test_statement_count_cc_scenario_1(self):
        stmts = _load("cc_scenario_1.json")
        root = convert(stmts)
        children = list(root)
        assert len(children) == 3  # 1 entity + 1 person + 1 OOC

    def test_entity_statement_fields(self):
        stmts = _load("cc_scenario_1.json")
        root = convert(stmts)
        entity = root.find("b:entityStatement", NS)
        assert entity is not None
        assert entity.findtext("b:statementType", namespaces=NS) == "entityStatement"
        assert entity.findtext("b:statementId", namespaces=NS) == "entity-12345678-canada-corp"

        # entityType
        assert entity.findtext(".//b:entityType", namespaces=NS) == "registeredEntity"

        # foundingDate
        assert entity.findtext("b:foundingDate", namespaces=NS) == "2021-05-11"

        # identifiers
        ids = entity.findall(".//b:identifier", NS)
        assert len(ids) == 2
        schemes = [i.findtext("b:scheme", namespaces=NS) for i in ids]
        assert "CA-BN" in schemes
        assert "CA-CC" in schemes

    def test_person_statement_fields(self):
        stmts = _load("cc_scenario_1.json")
        root = convert(stmts)
        person = root.find("b:personStatement", NS)
        assert person is not None
        assert person.findtext("b:personType", namespaces=NS) == "knownPerson"
        assert person.findtext("b:birthDate", namespaces=NS) == "2001-01-01"

        # names
        name = person.find(".//b:name", NS)
        assert name.findtext("b:fullName", namespaces=NS) == "Bob Orino"
        assert name.findtext("b:givenName", namespaces=NS) == "Bob"
        assert name.findtext("b:familyName", namespaces=NS) == "Orino"

    def test_ooc_statement_interests(self):
        stmts = _load("cc_scenario_1.json")
        root = convert(stmts)
        ooc = root.find("b:ownershipOrControlStatement", NS)
        assert ooc is not None

        interests = ooc.findall(".//b:interest", NS)
        assert len(interests) == 2

        # Share interest
        share_int = interests[0]
        assert share_int.findtext("b:type", namespaces=NS) == "share"
        assert share_int.findtext("b:directOrIndirect", namespaces=NS) == "direct"
        assert share_int.findtext(".//b:exact", namespaces=NS) == "25"

        # Board chair interest
        board_int = interests[1]
        assert board_int.findtext("b:type", namespaces=NS) == "boardChair"
        assert board_int.findtext("b:details", namespaces=NS) == "Chair of the board. Calls the shots."

    def test_ooc_subject_and_interested_party_refs(self):
        stmts = _load("cc_scenario_1.json")
        root = convert(stmts)
        ooc = root.find("b:ownershipOrControlStatement", NS)

        subj = ooc.find("b:subject", NS)
        assert subj.findtext("b:describedByEntityStatement", namespaces=NS) == "entity-12345678-canada-corp"

        ip = ooc.find("b:interestedParty", NS)
        assert ip.findtext("b:describedByPersonStatement", namespaces=NS) == "person-bob-orino"

    def test_multiple_bos_cc_scenario_2(self):
        stmts = _load("cc_scenario_2.json")
        root = convert(stmts)
        persons = root.findall("b:personStatement", NS)
        assert len(persons) == 2

        oocs = root.findall("b:ownershipOrControlStatement", NS)
        assert len(oocs) == 2

    def test_entity_bo_qc_scenario_2(self):
        stmts = _load("qc_scenario_2_entity_bo.json")
        root = convert(stmts)
        entities = root.findall("b:entityStatement", NS)
        assert len(entities) == 2  # subject + shell corp

        ooc = root.find("b:ownershipOrControlStatement", NS)
        ip = ooc.find("b:interestedParty", NS)
        # Interested party is an entity, not a person
        assert ip.findtext("b:describedByEntityStatement", namespaces=NS) == "entity-valcour-shell"

        interest = ooc.find(".//b:interest", NS)
        assert interest.findtext("b:type", namespaces=NS) == "controlByLegalFramework"

    def test_exempt_interest_type(self):
        stmts = _load("qc_scenario_5_exempt.json")
        root = convert(stmts)
        ooc = root.find("b:ownershipOrControlStatement", NS)
        interest = ooc.find(".//b:interest", NS)
        assert interest.findtext("b:type", namespaces=NS) == "exempt"
        assert interest.findtext("b:directOrIndirect", namespaces=NS) == "indirect"

    def test_unknown_proximity_bc_scenario_1(self):
        stmts = _load("bc_scenario_1.json")
        root = convert(stmts)
        ooc = root.find("b:ownershipOrControlStatement", NS)
        interest = ooc.find(".//b:interest", NS)
        assert interest.findtext("b:directOrIndirect", namespaces=NS) == "unknown"
        assert interest.findtext("b:startDate", namespaces=NS) == "2011-09-09"
        assert interest.findtext("b:endDate", namespaces=NS) == "2021-05-19"

    def test_tax_residencies(self):
        stmts = _load("bc_scenario_1.json")
        root = convert(stmts)
        person = root.find("b:personStatement", NS)
        tr = person.findall(".//b:taxResidency", NS)
        assert len(tr) == 1

    def test_xml_is_well_formed_string(self):
        stmts = _load("cc_scenario_1.json")
        root = convert(stmts)
        xml_str = to_string(root)
        assert xml_str.startswith("<?xml")
        # Should be parseable
        etree.fromstring(xml_str.encode("utf-8"))

    def test_convert_file(self, tmp_path):
        src = FIXTURES / "cc_scenario_1.json"
        root = convert_file(src)
        assert root.tag == f"{{{BODS_NS}}}bodsDataset"

    def test_convert_jsonl(self, tmp_path):
        stmts = _load("cc_scenario_1.json")
        jsonl_file = tmp_path / "test.jsonl"
        jsonl_file.write_text("\n".join(json.dumps(s) for s in stmts))
        root = convert_file(jsonl_file)
        assert len(list(root)) == 3
