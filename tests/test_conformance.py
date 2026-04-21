"""Conformance tests using bods-fixtures canonical test pack.

Uses the pytest-bods-v04-fixtures plugin to auto-parametrize tests
across every fixture in the bods-fixtures package. Each fixture is
run through both the canonical and MRAS converters to verify they
produce valid, well-formed XML without errors.

Install: pip install pytest-bods-v04-fixtures
"""

from lxml import etree

from bods_xml.canonical import convert as canonical_convert, to_string as canonical_to_string, BODS_NS
from bods_xml.profiles.mras import convert as mras_convert, to_string as mras_to_string, PREBODS_NS


class TestCanonicalConformance:
    """Every bods-fixture should convert to valid canonical XML."""

    def test_converts_without_error(self, bods_fixture):
        root = canonical_convert(bods_fixture.statements)
        assert root is not None
        assert root.tag == f"{{{BODS_NS}}}bodsDataset"

    def test_produces_well_formed_xml(self, bods_fixture):
        root = canonical_convert(bods_fixture.statements)
        xml_str = canonical_to_string(root)
        assert xml_str.startswith("<?xml")
        # Round-trip parse to confirm well-formedness
        parsed = etree.fromstring(xml_str.encode("utf-8"))
        assert parsed.tag == f"{{{BODS_NS}}}bodsDataset"

    def test_statement_count_matches(self, bods_fixture):
        root = canonical_convert(bods_fixture.statements)
        children = list(root)
        assert len(children) == len(bods_fixture.statements)


class TestMrasConformance:
    """Every bods-fixture should convert to valid MRAS preBODS XML."""

    def test_converts_without_error(self, bods_fixture):
        root = mras_convert(bods_fixture.statements,
                           record_timestamp="2024-01-01T00:00:00Z")
        assert root is not None
        assert root.tag == f"{{{PREBODS_NS}}}preBODS"

    def test_produces_well_formed_xml(self, bods_fixture):
        root = mras_convert(bods_fixture.statements,
                           record_timestamp="2024-01-01T00:00:00Z")
        xml_str = mras_to_string(root)
        assert xml_str.startswith("<?xml")
        # Round-trip parse to confirm well-formedness
        parsed = etree.fromstring(xml_str.encode("utf-8"))
        assert parsed.tag == f"{{{PREBODS_NS}}}preBODS"

    def test_has_record_timestamp(self, bods_fixture):
        root = mras_convert(bods_fixture.statements,
                           record_timestamp="2024-01-01T00:00:00Z")
        ts = root.findtext(f"{{{PREBODS_NS}}}record_timestamp")
        assert ts == "2024-01-01T00:00:00Z"
