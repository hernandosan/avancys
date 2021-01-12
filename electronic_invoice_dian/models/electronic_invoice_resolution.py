# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from lxml import etree
import requests
import re
import json
import base64
import operator
from functools import reduce
from .http_helper import URL_NUMBERING_XML, AVANCYS_NIT, HEADERS

ID_PARAM_HELP = """Provisto por el Proveedor Tecnológico"""
DOCUMENT_TYPE_HELP = """
Para Notas Crédito y Débito los datos de resolución no aplican"""
DOCUMENT_TYPE_SELECTION = [
    ('01', 'Factura Electrónica'),
    ('91', 'Nota Crédito'),
    ('92', 'Nota Débito'),
    ('03', 'Contingencia')
]

# Warnings

NOT_ENOUGH_DATA_WARN = """
No hay suficientes datos para obtener la información, Por favor ingrese
al menos los siguientes:

- Número de Resolución
- Prefijo
- Numeración Desde
- Numeración Hasta
"""
MULTI_RESOLUTION_WARN = """
Se encontro mas de una resolución con los mismos parametros.
"""
NO_RESOLUTION_WARN = """
No se encontro ninguna resolución que coincida con los datos."""
RESOLUTION_SAMPLE = """
Ejemplo: Resolución DIAN N° 00000000 desde PREFIJO 1 hasta PREFIJO 1000
"""


class ElectronicInvoiceResolution(models.Model):
    _name = 'electronic.invoice.resolution'
    _description = 'Resolucion de Facturacion Electronica'

    name = fields.Char(string='Nombre', required=True)
    number = fields.Char(string='Número de Resolución')
    prefix = fields.Char('Prefijo', required=True)
    from_number = fields.Integer(string='Numeración Desde', copy=False)
    to_number = fields.Integer(string='Numeración Hasta', copy=False)
    valid_date_from = fields.Date(string='Fecha Inicio Resolución', copy=False)
    valid_date_to = fields.Date(string='Fecha Fin Resolución', copy=False)
    id_param = fields.Integer(
        string='ID Resolución', help=ID_PARAM_HELP, required=True, default=0)
    technical_key = fields.Char(string='Clave Técnica', copy=False)
    document_type = fields.Selection(
        string='Tipo de Documento', selection=DOCUMENT_TYPE_SELECTION,
        required=True, copy=False, help=DOCUMENT_TYPE_HELP)
    description = fields.Text(
        string='Texto de Resolución', placeholder=RESOLUTION_SAMPLE)
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.company,
        index=True, required=True)

    def get_resolution_xml(self):
        self.ensure_one()
        company = self.company_id
        body_dict = {
            "datos_conexion":
                {
                    "token": company.software_token,
                    "documento": company.partner_id.ref_num,
                    "documentoT": (AVANCYS_NIT
                                   if company.ei_software_operation == 'provider'
                                   else company.partner_id.ref_num)
                },
            "Datos_software":
                {
                    "codigo": company.software_code_dian,
                    "ambiente": "1"
                }
        }
        data = 'json_data=' + \
            base64.b64encode(json.dumps(body_dict).encode(
                'utf-8')).decode('utf-8')
        response = requests.post(URL_NUMBERING_XML, data=data,
                                 headers=HEADERS, verify=False)
        return str(response.content, 'utf-8')

    def parse_resolution(self, resolution):
        return {
            'ResolutionNumber': re.search(
                r'<c:ResolutionNumber>(.*?)</c:ResolutionNumber>', resolution).group(1),
            'ResolutionDate': re.search(
                r'<c:ResolutionDate>(.*?)</c:ResolutionDate>', resolution).group(1),
            'Prefix': re.search(r'<c:Prefix>(.*?)</c:Prefix>', resolution).group(1),
            'FromNumber': re.search(r'<c:FromNumber>(.*?)</c:FromNumber>', resolution).group(1),
            'ToNumber': re.search(r'<c:ToNumber>(.*?)</c:ToNumber>', resolution).group(1),
            'ValidDateFrom': re.search(
                r'<c:ValidDateFrom>(.*?)</c:ValidDateFrom>', resolution).group(1),
            'ValidDateTo': re.search(r'<c:ValidDateTo>(.*?)</c:ValidDateTo>', resolution).group(1),
            'TechnicalKey': re.search(r'<c:TechnicalKey>(.*?)</c:TechnicalKey>',
                                      resolution).group(1)
        }

    def resolucion_match(self, resolucion_match):
        return reduce(operator.and_, [
            self.number == resolucion_match.get('ResolutionNumber', False),
            self.prefix == resolucion_match.get('Prefix', False),
            str(self.from_number) == resolucion_match.get('FromNumber', False),
            str(self.to_number) == resolucion_match.get('ToNumber', False),
        ])

    def get_technical_key(self):
        if not self.prefix or not self.number or not self.from_number or not self.to_number:
            raise ValidationError(NOT_ENOUGH_DATA_WARN)
        self.technical_key = ''
        resolution_xml = self.get_resolution_xml()
        resolutions = re.findall(
            r'<c:NumberRangeResponse>([\s\S.]*?)</c:NumberRangeResponse>', resolution_xml)
        if not resolutions:
            return
        resolutions_list = list(map(self.parse_resolution, resolutions))
        matching_resolution = list(
            filter(self.resolucion_match, resolutions_list))
        if not matching_resolution:
            raise ValidationError(NO_RESOLUTION_WARN)
        if len(matching_resolution) > 1:
            raise ValidationError(MULTI_RESOLUTION_WARN)
        self.technical_key = matching_resolution[0]['TechnicalKey']
