"""Canonical BODS 0.4 JSON → XML converter.

Produces a faithful XML serialisation of BODS 0.4 data, preserving all fields
and structure. The canonical XML uses the namespace:

    https://standard.openownership.org/ns/0.4

Every BODS JSON field maps to an XML element with the same camelCase name.
Arrays become repeating child elements. The top-level container is <bodsDataset>.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lxml import etree

# Canonical BODS XML namespace
BODS_NS = "https://standard.openownership.org/ns/0.4"
NSMAP = {None: BODS_NS}


def _el(parent: etree._Element | None, tag: str, text: str | None = None,
        attrib: dict | None = None) -> etree._Element:
    """Create a namespaced element, optionally appending to parent."""
    elem = etree.SubElement(parent, f"{{{BODS_NS}}}{tag}") if parent is not None else etree.Element(f"{{{BODS_NS}}}{tag}", nsmap=NSMAP)
    if text is not None:
        elem.text = str(text)
    if attrib:
        for k, v in attrib.items():
            elem.set(k, str(v))
    return elem


# ---------------------------------------------------------------------------
# Field-level serialisers
# ---------------------------------------------------------------------------

def _add_identifier(parent: etree._Element, ident: dict) -> None:
    el = _el(parent, "identifier")
    if "scheme" in ident:
        _el(el, "scheme", ident["scheme"])
    if "id" in ident:
        _el(el, "id", ident["id"])
    if "schemeName" in ident:
        _el(el, "schemeName", ident["schemeName"])
    if "uri" in ident:
        _el(el, "uri", ident["uri"])


def _add_name(parent: etree._Element, name: dict) -> None:
    el = _el(parent, "name")
    if "type" in name:
        _el(el, "type", name["type"])
    if "fullName" in name:
        _el(el, "fullName", name["fullName"])
    if "givenName" in name:
        _el(el, "givenName", name["givenName"])
    if "familyName" in name:
        _el(el, "familyName", name["familyName"])
    if "patronymicName" in name:
        _el(el, "patronymicName", name["patronymicName"])


def _add_address(parent: etree._Element, addr: dict) -> None:
    el = _el(parent, "address")
    for field in ("type", "address", "postCode", "country"):
        if field in addr:
            _el(el, field, addr[field])


def _add_jurisdiction(parent: etree._Element, tag: str, jur: dict | str) -> None:
    if isinstance(jur, str):
        _el(parent, tag, jur)
    elif isinstance(jur, dict):
        el = _el(parent, tag)
        if "code" in jur:
            _el(el, "code", jur["code"])
        if "name" in jur:
            _el(el, "name", jur["name"])


def _add_share(parent: etree._Element, share: dict) -> None:
    el = _el(parent, "share")
    for field in ("exact", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"):
        if field in share:
            _el(el, field, str(share[field]))


def _add_interest(parent: etree._Element, interest: dict) -> None:
    el = _el(parent, "interest")
    if "type" in interest:
        _el(el, "type", interest["type"])
    if "directOrIndirect" in interest:
        _el(el, "directOrIndirect", interest["directOrIndirect"])
    if "beneficialOwnershipOrControl" in interest:
        _el(el, "beneficialOwnershipOrControl",
            str(interest["beneficialOwnershipOrControl"]).lower())
    if "details" in interest:
        _el(el, "details", interest["details"])
    if "share" in interest:
        _add_share(el, interest["share"])
    if "startDate" in interest:
        _el(el, "startDate", interest["startDate"])
    if "endDate" in interest:
        _el(el, "endDate", interest["endDate"])


def _add_source(parent: etree._Element, source: dict) -> None:
    el = _el(parent, "source")
    for field in ("type", "description", "url", "retrievedAt", "assertedBy"):
        if field in source:
            _el(el, field, source[field])


def _add_publication_details(parent: etree._Element, pub: dict) -> None:
    el = _el(parent, "publicationDetails")
    if "publicationDate" in pub:
        _el(el, "publicationDate", pub["publicationDate"])
    if "bodsVersion" in pub:
        _el(el, "bodsVersion", pub["bodsVersion"])
    if "license" in pub:
        _el(el, "license", pub["license"])
    if "publisher" in pub:
        pub_el = _el(el, "publisher")
        for field in ("name", "url"):
            if field in pub["publisher"]:
                _el(pub_el, field, pub["publisher"][field])


def _add_pep_status(parent: etree._Element, pep: dict) -> None:
    el = _el(parent, "pepStatus")
    for field in ("status", "details", "jurisdiction", "startDate", "endDate",
                  "source"):
        if field in pep:
            if field == "jurisdiction":
                _add_jurisdiction(el, "jurisdiction", pep[field])
            elif field == "source":
                _add_source(el, pep[field])
            else:
                _el(el, field, pep[field])


# ---------------------------------------------------------------------------
# Statement-level serialisers
# ---------------------------------------------------------------------------

def _add_common_fields(el: etree._Element, stmt: dict) -> None:
    """Add fields common to all statement types."""
    if "statementId" in stmt:
        _el(el, "statementId", stmt["statementId"])
    if "statementType" in stmt:
        _el(el, "statementType", stmt["statementType"])
    if "statementDate" in stmt:
        _el(el, "statementDate", stmt["statementDate"])
    if "isComponent" in stmt:
        _el(el, "isComponent", str(stmt["isComponent"]).lower())
    if "componentStatementIDs" in stmt:
        ids_el = _el(el, "componentStatementIDs")
        for cid in stmt["componentStatementIDs"]:
            _el(ids_el, "componentStatementID", cid)
    if "publicationDetails" in stmt:
        _add_publication_details(el, stmt["publicationDetails"])
    if "source" in stmt:
        _add_source(el, stmt["source"])
    if "replacesStatements" in stmt:
        rep_el = _el(el, "replacesStatements")
        for rid in stmt["replacesStatements"]:
            _el(rep_el, "replacesStatement", rid)


def serialize_person_statement(stmt: dict) -> etree._Element:
    """Serialize a BODS personStatement to canonical XML."""
    el = etree.Element(f"{{{BODS_NS}}}personStatement", nsmap=NSMAP)
    _add_common_fields(el, stmt)

    rd = stmt.get("recordDetails", stmt)

    if "personType" in rd:
        _el(el, "personType", rd["personType"])

    if "names" in rd:
        names_el = _el(el, "names")
        for name in rd["names"]:
            _add_name(names_el, name)

    if "identifiers" in rd:
        ids_el = _el(el, "identifiers")
        for ident in rd["identifiers"]:
            _add_identifier(ids_el, ident)

    if "nationalities" in rd:
        nats_el = _el(el, "nationalities")
        for nat in rd["nationalities"]:
            _add_jurisdiction(nats_el, "nationality", nat)

    if "birthDate" in rd:
        _el(el, "birthDate", rd["birthDate"])

    if "placeOfBirth" in rd:
        _el(el, "placeOfBirth", rd["placeOfBirth"])

    if "addresses" in rd:
        addrs_el = _el(el, "addresses")
        for addr in rd["addresses"]:
            _add_address(addrs_el, addr)

    if "taxResidencies" in rd:
        tr_el = _el(el, "taxResidencies")
        for tr in rd["taxResidencies"]:
            _add_jurisdiction(tr_el, "taxResidency", tr)

    if "hasPepStatus" in rd:
        _el(el, "hasPepStatus", str(rd["hasPepStatus"]).lower())

    if "pepStatusDetails" in rd:
        psd_el = _el(el, "pepStatusDetails")
        for pep in rd["pepStatusDetails"]:
            _add_pep_status(psd_el, pep)

    return el


def serialize_entity_statement(stmt: dict) -> etree._Element:
    """Serialize a BODS entityStatement to canonical XML."""
    el = etree.Element(f"{{{BODS_NS}}}entityStatement", nsmap=NSMAP)
    _add_common_fields(el, stmt)

    rd = stmt.get("recordDetails", stmt)

    if "entityType" in rd:
        _el(el, "entityType", rd["entityType"])

    if "names" in rd:
        names_el = _el(el, "names")
        for name in rd["names"]:
            _add_name(names_el, name)

    if "identifiers" in rd:
        ids_el = _el(el, "identifiers")
        for ident in rd["identifiers"]:
            _add_identifier(ids_el, ident)

    if "incorporatedInJurisdiction" in rd:
        _add_jurisdiction(el, "incorporatedInJurisdiction",
                         rd["incorporatedInJurisdiction"])

    if "foundingDate" in rd:
        _el(el, "foundingDate", rd["foundingDate"])

    if "dissolutionDate" in rd:
        _el(el, "dissolutionDate", rd["dissolutionDate"])

    if "addresses" in rd:
        addrs_el = _el(el, "addresses")
        for addr in rd["addresses"]:
            _add_address(addrs_el, addr)

    if "isComponent" not in el.attrib and "isComponent" in rd:
        _el(el, "isComponent", str(rd["isComponent"]).lower())

    return el


def serialize_ooc_statement(stmt: dict) -> etree._Element:
    """Serialize a BODS ownershipOrControlStatement to canonical XML."""
    el = etree.Element(f"{{{BODS_NS}}}ownershipOrControlStatement", nsmap=NSMAP)
    _add_common_fields(el, stmt)

    rd = stmt.get("recordDetails", stmt)

    if "subject" in rd:
        subj = rd["subject"]
        subj_el = _el(el, "subject")
        if isinstance(subj, str):
            _el(subj_el, "describedByEntityStatement", subj)
        elif isinstance(subj, dict):
            if "describedByEntityStatement" in subj:
                _el(subj_el, "describedByEntityStatement",
                    subj["describedByEntityStatement"])

    if "interestedParty" in rd:
        ip = rd["interestedParty"]
        ip_el = _el(el, "interestedParty")
        if isinstance(ip, str):
            # Could be person or entity ref — use generic element
            _el(ip_el, "describedByStatement", ip)
        elif isinstance(ip, dict):
            if "describedByPersonStatement" in ip:
                _el(ip_el, "describedByPersonStatement",
                    ip["describedByPersonStatement"])
            elif "describedByEntityStatement" in ip:
                _el(ip_el, "describedByEntityStatement",
                    ip["describedByEntityStatement"])
            elif "unspecified" in ip:
                unspec = ip["unspecified"]
                unspec_el = _el(ip_el, "unspecified")
                if isinstance(unspec, dict):
                    if "reason" in unspec:
                        _el(unspec_el, "reason", unspec["reason"])
                    if "description" in unspec:
                        _el(unspec_el, "description", unspec["description"])

    if "interests" in rd:
        interests_el = _el(el, "interests")
        for interest in rd["interests"]:
            _add_interest(interests_el, interest)

    return el


# ---------------------------------------------------------------------------
# Top-level conversion
# ---------------------------------------------------------------------------

SERIALIZERS = {
    "personStatement": serialize_person_statement,
    "entityStatement": serialize_entity_statement,
    "ownershipOrControlStatement": serialize_ooc_statement,
}


def convert(statements: list[dict]) -> etree._Element:
    """Convert a list of BODS 0.4 statement dicts to a canonical XML tree.

    Args:
        statements: List of BODS statement dicts (the JSON array contents).

    Returns:
        lxml Element tree rooted at <bodsDataset>.
    """
    root = etree.Element(f"{{{BODS_NS}}}bodsDataset", nsmap=NSMAP)

    for stmt in statements:
        stmt_type = stmt.get("statementType")
        # BODS 0.4 uses recordType at top level, recordDetails for payload
        if not stmt_type:
            stmt_type = stmt.get("recordType")
        if stmt_type and stmt_type in SERIALIZERS:
            elem = SERIALIZERS[stmt_type](stmt)
            root.append(elem)

    return root


def convert_json_string(json_str: str) -> etree._Element:
    """Convert a BODS JSON string to canonical XML."""
    data = json.loads(json_str)
    if isinstance(data, list):
        return convert(data)
    elif isinstance(data, dict):
        return convert([data])
    raise ValueError("BODS data must be a JSON array or single statement object")


def convert_file(input_path: str | Path) -> etree._Element:
    """Convert a BODS JSON or JSONL file to canonical XML.

    Supports:
        - .json files containing a JSON array of statements
        - .jsonl files with one statement per line
    """
    path = Path(input_path)
    text = path.read_text(encoding="utf-8")

    if path.suffix == ".jsonl":
        statements = []
        for line in text.strip().splitlines():
            line = line.strip()
            if line:
                statements.append(json.loads(line))
        return convert(statements)
    else:
        return convert_json_string(text)


def to_string(root: etree._Element, pretty_print: bool = True) -> str:
    """Serialize an XML element tree to a UTF-8 string."""
    return etree.tostring(
        root,
        pretty_print=pretty_print,
        xml_declaration=True,
        encoding="UTF-8",
    ).decode("utf-8")
