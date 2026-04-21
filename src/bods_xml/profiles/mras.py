"""MRAS preBODS output profile.

Converts BODS 0.4 JSON statements into the MRAS preBODS XML format used by
Canada's Multijurisdictional Registry Access Service for the BOP2P
(Beneficial Ownership Policy to Practice) programme.

The preBODS format (namespace http://mras.ca/schema/preBODS) restructures
BODS's flat statement array into a hierarchical document:

    <preBODS>
        <record_timestamp>...</record_timestamp>
        <entityRecord isSubject=true>...</entityRecord>     <- the subject entity
        <relationshipPair>                                   <- one per BO relationship
            <personRecord>...</personRecord>                 <- or <entityRecord>
            <relationshipRecord>...</relationshipRecord>
        </relationshipPair>
        ...
        <entityRecord isSubject=false>...</entityRecord>     <- linked entities (XP/HJ)
    </preBODS>

Key structural differences from canonical BODS XML:
    - Statements are bundled into relationshipPairs rather than flat
    - No statementIds or cross-references; structure is implicit
    - Person identifiers use scheme-less types (SIN, ITN)
    - Addresses are flattened into a single addressLine
    - Nationality/taxResidency use code+name pairs
    - beneficialOwnershipOrControl is an explicit boolean field
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lxml import etree

PREBODS_NS = "http://mras.ca/schema/preBODS"
NSMAP = {None: PREBODS_NS}


def _el(parent: etree._Element | None, tag: str, text: str | None = None) -> etree._Element:
    """Create a namespaced preBODS element."""
    if parent is not None:
        elem = etree.SubElement(parent, f"{{{PREBODS_NS}}}{tag}")
    else:
        elem = etree.Element(f"{{{PREBODS_NS}}}{tag}", nsmap=NSMAP)
    if text is not None:
        elem.text = str(text)
    return elem


# ---------------------------------------------------------------------------
# Identifier scheme mapping: BODS org-id.guide -> MRAS identifier types
# ---------------------------------------------------------------------------

# BODS uses org-id.guide scheme codes; MRAS preBODS uses short type strings.
# This mapping covers the Canadian identifier schemes seen in the sd-exploration files.
# SIN (Social Insurance Number) and ITN (Individual Tax Number) are person identifiers
# that don't have org-id.guide codes -- they appear in BODS as custom scheme values.
BODS_SCHEME_TO_MRAS_TYPE = {
    "CA-SIN": "SIN",
    "CA-ITN": "ITN",
}

# Reverse: for identifier types that appear in source data without scheme codes
MRAS_TYPE_FALLBACK = {"SIN", "ITN"}


def _map_identifier_type(identifier: dict) -> str | None:
    """Map a BODS identifier to an MRAS identifier type string."""
    scheme = identifier.get("scheme", "")
    if scheme in BODS_SCHEME_TO_MRAS_TYPE:
        return BODS_SCHEME_TO_MRAS_TYPE[scheme]
    # If the schemeName or scheme itself looks like an MRAS type, use it directly
    scheme_name = identifier.get("schemeName", scheme)
    if scheme_name in MRAS_TYPE_FALLBACK:
        return scheme_name
    # Fall back to the scheme code itself
    return scheme if scheme else None


# ---------------------------------------------------------------------------
# Entity record serialisation
# ---------------------------------------------------------------------------

def _add_entity_record(parent: etree._Element, stmt: dict,
                       is_subject: bool = False,
                       xp_type: str | None = None,
                       jurisdiction: dict | None = None) -> etree._Element:
    """Serialize a BODS entityStatement into a preBODS <entityRecord>."""
    el = _el(parent, "entityRecord")

    rd = stmt.get("recordDetails", stmt)

    _el(el, "isSubject", "true" if is_subject else "false")

    if not is_subject and xp_type:
        _el(el, "xpType", xp_type)

    # recordDate -- use statementDate or publicationDetails date
    # Standalone XP entities (linked registrations) don't carry recordDate
    # in the preBODS format; only subject entities, person records, and
    # entity BOs in relationship pairs do.
    if not xp_type:
        record_date = stmt.get("statementDate")
        if not record_date:
            pub = stmt.get("publicationDetails", {})
            record_date = pub.get("publicationDate")
        if record_date:
            _el(el, "recordDate", record_date)

    # entityType
    entity_type = rd.get("entityType", "registeredEntity")
    _el(el, "entityType", entity_type)

    # name -- take the first name's fullName, or the first name object
    names = rd.get("names", [])
    if names:
        name_obj = names[0]
        name_str = name_obj.get("fullName") or name_obj.get("name", "")
        _el(el, "name", name_str)

    # foundingDate
    if "foundingDate" in rd:
        _el(el, "foundingDate", rd["foundingDate"])

    # identifiers
    identifiers = rd.get("identifiers", [])
    if identifiers:
        ids_el = _el(el, "identifiers")
        for ident in identifiers:
            id_el = _el(ids_el, "identifier")
            scheme = ident.get("scheme", "")
            _el(id_el, "scheme", scheme)
            _el(id_el, "id", ident.get("id", ""))

    # jurisdiction (for non-subject entities)
    if not is_subject:
        jur = jurisdiction or rd.get("incorporatedInJurisdiction")
        if jur:
            jur_el = _el(el, "jurisdiction")
            if isinstance(jur, str):
                _el(jur_el, "code", jur)
                _el(jur_el, "name", jur)
            elif isinstance(jur, dict):
                _el(jur_el, "code", jur.get("code", ""))
                _el(jur_el, "name", jur.get("name", jur.get("code", "")))

    return el


# ---------------------------------------------------------------------------
# Person record serialisation
# ---------------------------------------------------------------------------

def _add_person_record(parent: etree._Element, stmt: dict) -> etree._Element:
    """Serialize a BODS personStatement into a preBODS <personRecord>."""
    el = _el(parent, "personRecord")

    rd = stmt.get("recordDetails", stmt)

    # recordDate
    record_date = stmt.get("statementDate")
    if not record_date:
        pub = stmt.get("publicationDetails", {})
        record_date = pub.get("publicationDate")
    if record_date:
        _el(el, "recordDate", record_date)

    # personType
    person_type = rd.get("personType", "knownPerson")
    _el(el, "personType", person_type)

    # nationalities
    nats = rd.get("nationalities", [])
    if nats:
        nats_el = _el(el, "nationalities")
        for nat in nats:
            nat_el = _el(nats_el, "nationality")
            code = nat.get("code", nat) if isinstance(nat, dict) else str(nat)
            name = nat.get("name", code) if isinstance(nat, dict) else str(nat)
            _el(nat_el, "code", code)
            _el(nat_el, "name", name)

    # taxResidencies
    tax_res = rd.get("taxResidencies", [])
    if tax_res:
        tr_el = _el(el, "taxResidencies")
        for tr in tax_res:
            tres_el = _el(tr_el, "taxResidency")
            code = tr.get("code", tr) if isinstance(tr, dict) else str(tr)
            name = tr.get("name", code) if isinstance(tr, dict) else str(tr)
            _el(tres_el, "code", code)
            _el(tres_el, "name", name)

    # names
    names = rd.get("names", [])
    if names:
        name_obj = names[0]
        names_el = _el(el, "names")
        name_type = name_obj.get("type", "individual")
        _el(names_el, "type", name_type)
        full = name_obj.get("fullName", "")
        given = name_obj.get("givenName", "")
        family = name_obj.get("familyName", "")
        if not full and given and family:
            full = f"{given} {family}"
        _el(names_el, "fullName", full)
        if given:
            _el(names_el, "givenName", given)
        if family:
            _el(names_el, "familyName", family)

    # birthDate
    if "birthDate" in rd:
        _el(el, "birthDate", rd["birthDate"])

    # addresses -- flatten to addressLine
    addrs = rd.get("addresses", [])
    if addrs:
        addrs_el = _el(el, "addresses")
        for addr in addrs:
            addr_el = _el(addrs_el, "address")
            _el(addr_el, "type", addr.get("type", "TBD"))
            # Build addressLine from structured fields if available
            address_text = addr.get("address", "")
            _el(addr_el, "addressLine", address_text)
            country = addr.get("country", "")
            _el(addr_el, "country", country)
            postcode = addr.get("postCode", "")
            _el(addr_el, "postCode", postcode)

    return el


# ---------------------------------------------------------------------------
# Relationship record serialisation
# ---------------------------------------------------------------------------

def _add_relationship_record(parent: etree._Element, ooc_stmt: dict) -> etree._Element:
    """Serialize a BODS ownershipOrControlStatement into a preBODS <relationshipRecord>."""
    el = _el(parent, "relationshipRecord")

    rd = ooc_stmt.get("recordDetails", ooc_stmt)
    interests = rd.get("interests", [])

    if interests:
        interests_el = _el(el, "interests")
        for interest in interests:
            int_el = _el(interests_el, "interest")
            if "type" in interest:
                _el(int_el, "type", interest["type"])
            if "directOrIndirect" in interest:
                _el(int_el, "directOrIndirect", interest["directOrIndirect"])

            # beneficialOwnershipOrControl -- always included in preBODS
            bo_flag = interest.get("beneficialOwnershipOrControl", True)
            _el(int_el, "beneficialOwnershipOrControl",
                str(bo_flag).lower())

            # details
            details = interest.get("details", "")
            _el(int_el, "details", details if details else "")

            # dates (before share -- matches MRAS preBODS element order)
            if "startDate" in interest:
                _el(int_el, "startDate", interest["startDate"])
            if "endDate" in interest:
                _el(int_el, "endDate", interest["endDate"])

            # share
            if "share" in interest:
                share = interest["share"]
                share_el = _el(int_el, "share")
                for field in ("exact", "minimum", "maximum",
                              "exclusiveMinimum", "exclusiveMaximum"):
                    if field in share:
                        _el(share_el, field, str(share[field]))

    return el


# ---------------------------------------------------------------------------
# Top-level conversion
# ---------------------------------------------------------------------------

def convert(statements: list[dict],
            record_timestamp: str | None = None) -> etree._Element:
    """Convert BODS 0.4 statements to preBODS XML.

    Args:
        statements: List of BODS statement dicts.
        record_timestamp: ISO timestamp for the preBODS record_timestamp field.
            Defaults to current UTC time.

    Returns:
        lxml Element tree rooted at <preBODS>.
    """
    if record_timestamp is None:
        record_timestamp = datetime.now(timezone.utc).isoformat()

    root = etree.Element(f"{{{PREBODS_NS}}}preBODS", nsmap=NSMAP)
    _el(root, "record_timestamp", record_timestamp)

    # Index statements by ID and type
    by_id: dict[str, dict] = {}
    persons: list[dict] = []
    entities: list[dict] = []
    oocs: list[dict] = []

    for stmt in statements:
        stmt_type = stmt.get("statementType") or stmt.get("recordType")
        sid = stmt.get("statementId", "")
        if sid:
            by_id[sid] = stmt

        if stmt_type == "personStatement":
            persons.append(stmt)
        elif stmt_type == "entityStatement":
            entities.append(stmt)
        elif stmt_type == "ownershipOrControlStatement":
            oocs.append(stmt)

    # Identify subject entity: the entity referenced as 'subject' in OOC statements
    subject_ids = set()
    for ooc in oocs:
        rd = ooc.get("recordDetails", ooc)
        subj = rd.get("subject", {})
        if isinstance(subj, str):
            subject_ids.add(subj)
        elif isinstance(subj, dict):
            subject_ids.add(subj.get("describedByEntityStatement", ""))

    # Find the subject entity statement
    subject_entity = None
    non_subject_entities = []
    for ent in entities:
        sid = ent.get("statementId", "")
        if sid in subject_ids:
            subject_entity = ent
        else:
            non_subject_entities.append(ent)

    # If no OOC statements, take the first entity as subject
    if subject_entity is None and entities:
        subject_entity = entities[0]
        non_subject_entities = entities[1:]

    # Emit subject entity record
    if subject_entity:
        _add_entity_record(root, subject_entity, is_subject=True)

    # Emit relationship pairs: match each OOC to its interested party
    for ooc in oocs:
        rd = ooc.get("recordDetails", ooc)
        ip = rd.get("interestedParty", {})

        # Resolve interested party
        ip_id = None
        ip_is_person = True
        if isinstance(ip, str):
            ip_id = ip
        elif isinstance(ip, dict):
            if "describedByPersonStatement" in ip:
                ip_id = ip["describedByPersonStatement"]
                ip_is_person = True
            elif "describedByEntityStatement" in ip:
                ip_id = ip["describedByEntityStatement"]
                ip_is_person = False

        ip_stmt = by_id.get(ip_id, {}) if ip_id else {}

        pair_el = _el(root, "relationshipPair")

        if ip_is_person and ip_stmt:
            _add_person_record(pair_el, ip_stmt)
        elif not ip_is_person and ip_stmt:
            _add_entity_record(pair_el, ip_stmt, is_subject=False)

        _add_relationship_record(pair_el, ooc)

    # Emit non-subject entities that aren't interested parties
    # (linked entities -- XP registrations, HJ references)
    ip_ids = set()
    for ooc in oocs:
        rd = ooc.get("recordDetails", ooc)
        ip = rd.get("interestedParty", {})
        if isinstance(ip, str):
            ip_ids.add(ip)
        elif isinstance(ip, dict):
            for key in ("describedByPersonStatement", "describedByEntityStatement"):
                if key in ip:
                    ip_ids.add(ip[key])

    for ent in non_subject_entities:
        sid = ent.get("statementId", "")
        if sid not in ip_ids:
            # Standalone non-subject entities are XP (extra-provincial)
            # or HJ (home jurisdiction) linked registrations
            _add_entity_record(root, ent, is_subject=False, xp_type="XP")

    return root


def convert_file(input_path: str | Path,
                 record_timestamp: str | None = None) -> etree._Element:
    """Convert a BODS JSON/JSONL file to preBODS XML."""
    path = Path(input_path)
    text = path.read_text(encoding="utf-8")

    if path.suffix == ".jsonl":
        statements = []
        for line in text.strip().splitlines():
            line = line.strip()
            if line:
                statements.append(json.loads(line))
    else:
        data = json.loads(text)
        statements = data if isinstance(data, list) else [data]

    return convert(statements, record_timestamp=record_timestamp)


def to_string(root: etree._Element, pretty_print: bool = True) -> str:
    """Serialize preBODS XML to a UTF-8 string."""
    return etree.tostring(
        root,
        pretty_print=pretty_print,
        xml_declaration=True,
        encoding="UTF-8",
    ).decode("utf-8")
