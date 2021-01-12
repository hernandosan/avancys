"""
Namespaces declarations
"""

NAMESPACES = {
    'ds': "http://www.w3.org/2000/09/xmldsig#",
    'cac': "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    'cbc': "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    'ccts': "urn:un:unece:uncefact:data:specification:CoreComponentTypeSchemaModule:2",
    'ext': "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    'xades': "http://uri.etsi.org/01903/v1.3.2#",
    'xades141': "http://uri.etsi.org/01903/v1.4.1#"
}

ATTDOC_ATTRS = {
    "xmlns:ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "xmlns": "urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2",
}
cac = '{%s}' % NAMESPACES['cac']
cbc = '{%s}' % NAMESPACES['cbc']
ccts = '{%s}' % NAMESPACES['ccts']
ext = '{%s}' % NAMESPACES['ext']
xades = '{%s}' % NAMESPACES['xades']
xades141 = '{%s}' % NAMESPACES['xades141']
ds = 'ds:'


class DictMap(dict):
    __getattr__ = dict.__getitem__


PREFIXMAP = {
    'cac': cac,
    'cbc': cbc,
    'ccts': ccts,
    'ext': ext,
    'xades': xades,
    'xades141': xades141,
}
Prefix = DictMap(PREFIXMAP)
