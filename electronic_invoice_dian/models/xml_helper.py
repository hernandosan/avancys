# -*- coding: utf-8 -*-
# pylint: disable=invalid-name, bare-except, eval-used, cell-var-from-loop
# pylint: disable=unused-wildcard-import,wildcard-import,too-many-locals
"""
XML Helper to build invoice
"""


from xml.etree.ElementTree import SubElement as ETSE
from xml.etree.ElementTree import Element as ETE
import xml.etree.ElementTree as ET
from .xml_schemas import ATTDOC_ATTRS
from .xml_schemas import Prefix as pfx
from .xml_schemas import NAMESPACES

for ns in NAMESPACES:
    ET.register_namespace(ns, NAMESPACES[ns])


def set_document_root(ET, doc_type):
    """Attachem Document Creation"""
    AttachedDocument = ET.Element(
        doc_type,
        attrib=ATTDOC_ATTRS
    )
    return AttachedDocument


def set_header(AttachedDocument, tags, tag_attributes):
    UBLVersionID = ET.SubElement(AttachedDocument, pfx.cbc + 'UBLVersionID')
    CustomizationID = ET.SubElement(
        AttachedDocument, pfx.cbc + 'CustomizationID')
    ProfileID = ET.SubElement(
        AttachedDocument, pfx.cbc + 'ProfileID')
    ProfileExecutionID = ET.SubElement(
        AttachedDocument, pfx.cbc + 'ProfileExecutionID')
    ID = ET.SubElement(
        AttachedDocument, pfx.cbc + 'ID')
    IssueDate = ET.SubElement(
        AttachedDocument, pfx.cbc + 'IssueDate')
    IssueTime = ET.SubElement(
        AttachedDocument, pfx.cbc + 'IssueTime')
    DocumentType = ET.SubElement(
        AttachedDocument, pfx.cbc + 'DocumentType')
    ParentDocumentID = ET.SubElement(
        AttachedDocument, pfx.cbc + 'ParentDocumentID')
    for tag in tags:
        try:
            eval(tag).text = tags[tag]
        except:
            pass
    return AttachedDocument


def set_party(Party, tags, tag_attributes):
    PartyTaxScheme = ET.SubElement(
        Party, pfx.cac + 'PartyTaxScheme')
    RegistrationName = ET.SubElement(
        PartyTaxScheme, pfx.cbc + 'RegistrationName')
    CompanyID = ET.SubElement(
        PartyTaxScheme, pfx.cbc + 'CompanyID',
        attrib=tag_attributes.get('CompanyID', {}))
    TaxLevelCode = ET.SubElement(
        PartyTaxScheme, pfx.cbc + 'TaxLevelCode',
        attrib=tag_attributes.get('TaxLevelCode', {}))
    TaxScheme = ET.SubElement(
        PartyTaxScheme, pfx.cac + 'TaxScheme')
    ID = ET.SubElement(
        TaxScheme, pfx.cbc + 'ID')
    Name = ET.SubElement(
        TaxScheme, pfx.cbc + 'Name')
    for tag in tags:
        try:
            eval(tag).text = tags[tag]
        except:
            pass
    return Party


def set_sender_party(AttachedDocument, values, tag_attributes):
    SenderParty = ET.SubElement(
        AttachedDocument, pfx.cac + 'SenderParty')
    set_party(SenderParty, values, tag_attributes)
    return AttachedDocument


def set_receiver_party(AttachedDocument, values, tag_attributes):
    ReceiverParty = ET.SubElement(
        AttachedDocument, pfx.cac + 'ReceiverParty')
    set_party(ReceiverParty, values, tag_attributes)
    return AttachedDocument


def set_attchment(Document, tags, tag_attributes):
    Attachment = ET.SubElement(
        Document, pfx.cac + 'Attachment')
    ExternalReference = ET.SubElement(
        Attachment, pfx.cac + 'ExternalReference')
    MimeCode = ET.SubElement(
        ExternalReference, pfx.cbc + 'MimeCode')
    EncodingCode = ET.SubElement(
        ExternalReference, pfx.cbc + 'EncodingCode')
    Description = ET.SubElement(
        ExternalReference, pfx.cbc + 'Description')
    for tag in tags:
        try:
            eval(tag).text = tags[tag]
        except:
            pass
    return Document


def set_parent_document_line_reference(AttachedDocument, tags, tag_attributes):
    ParentDocumentLineReference = ET.SubElement(
        AttachedDocument, pfx.cac + 'ParentDocumentLineReference')
    LineID = ET.SubElement(
        ParentDocumentLineReference, pfx.cbc + 'LineID')
    DocumentReference = ET.SubElement(
        ParentDocumentLineReference, pfx.cac + 'DocumentReference')
    ID = ET.SubElement(DocumentReference, pfx.cbc + 'ID')
    UUID = ET.SubElement(DocumentReference, pfx.cbc + 'UUID',
                         attrib=tag_attributes.get('UUID', {}))
    IssueDate = ET.SubElement(DocumentReference, pfx.cbc + 'IssueDate')
    DocumentType = ET.SubElement(DocumentReference, pfx.cbc + 'DocumentType')
    set_attchment(DocumentReference, tags, tag_attributes)
    ResultOfVerification = ET.SubElement(
        DocumentReference, pfx.cac + 'ResultOfVerification')
    ValidatorID = ET.SubElement(
        ResultOfVerification, pfx.cbc + 'ValidatorID')
    ValidationResultCode = ET.SubElement(
        ResultOfVerification, pfx.cbc + 'ValidationResultCode')
    ValidationDate = ET.SubElement(
        ResultOfVerification, pfx.cbc + 'ValidationDate')
    ValidationTime = ET.SubElement(
        ResultOfVerification, pfx.cbc + 'ValidationTime')
    for tag in tags:
        try:
            eval(tag).text = tags[tag]
        except:
            pass
    return AttachedDocument


def sanitize_utf_es(text):
    chars = {
        '&#241;': u'ñ', '&#225;': u'á', '&#233;': u'é', '&#237;': u'í',
        '&#243;': u'ó', '&#250;': u'ú', '&#193;': u'Á', '&#201;': u'É',
        '&#205;': u'Í', '&#211;': u'Ó', '&#218;': u'Ú'}
    sanitized_text = text
    for es_char, utf_char in chars.items():
        sanitized_text = sanitized_text.replace(es_char, utf_char)
    return sanitized_text


def build_xml_attached_document(xml_fe, app_response, values):
    xml_declaration = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    document = set_document_root(ET, doc_type='AttachedDocument')
    document = set_header(
        document, values['header']['tags'], values['header']['attrs'])
    document = set_sender_party(
        document, values['sender']['tags'], values['sender']['attrs'])
    document = set_receiver_party(
        document, values['receiver']['tags'], values['receiver']['attrs'])
    document = set_attchment(
        document, values['attachment']['tags'], values['attachment']['attrs'])
    document = set_parent_document_line_reference(
        document, values['doc_line']['tags'], values['doc_line']['attrs'])
    # return document
    doc_string = xml_declaration + ET.tostring(document).decode('utf-8').replace(
        'ei_xml_content', '<![CDATA[%s]]>' % xml_fe).replace(
            'ei_app_response', '<![CDATA[%s]]>' % app_response)
    return sanitize_utf_es(doc_string).encode('utf-8')
