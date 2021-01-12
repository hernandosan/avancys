# -*- coding: utf-8 -*-
from collections import OrderedDict
import base64
import json
import re
import requests


HEADERS = {
    'Host': 'facturaelectronica.avancyserp.com',
    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:72.0) Gecko/20100101 Firefox/72.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Referer': 'https://www.avancyserp.com/',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Content-Length': '5580',
    'Origin': 'https://www.avancyserp.com',
    'Connection': 'close',
    'Upgrade-Insecure-Requests': '1',
}


INVOICE = {
    "datos_conexion": {},
    "tipo_documento": {},
    "basicos_factura": {},
    "respuesta": {},
    "param_basico": {},
    "facturador": {},
    "autorizacion_descarga": {},
    "WithholdingTaxTotal": {},
    "datos_empresa": {},
    "datos_cliente": {},
    "datos_transportadora": {},
    "QR": {},
    "Periodo_pago": {},
    "Metodo_pago": {},
    "Referencia_factura": {},
    "Referencia_factura2": {},
    "respuesta_discrepancia": {},
    "order_de_referencia": {},
    "Referencia_envio": {},
    "Referencia_recibido": {},
    "Terminos_de_entrega": {},
    "Tasa_cambio": {},
    "AdditionalDocumentReference": {},
    "Anticipos": [],
    "Productos_servicios": []
}

URL_XML = 'https://facturaelectronica.avancyserp.com/facturacion_electronica/V5.0/xml/formatos/GetXmlByDocumentKey.php'
URL_NUMBERING_XML = 'https://facturaelectronica.avancyserp.com/facturacion_electronica/V5.1/xml/formatos/GetNumberingRange.php'
DEFAULT_SERVICE_POST = 'https://www.avancyserp.com/response_ajax.php'
DEFAULT_SERVICE_URL = 'https://facturaelectronica.avancyserp.com/facturacion_electronica/V5.0/send.php'
DEFAULT_SERVICE_URL_GET = 'https://facturaelectronica.avancyserp.com/facturacion_electronica/V5.0/view_response.php'
AVANCYS_NIT = 900297700
