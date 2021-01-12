# -*- coding: utf-8 -*-
from odoo import api, fields, models
from .http_helper import DEFAULT_SERVICE_URL
from .http_helper import DEFAULT_SERVICE_URL_GET
from .http_helper import DEFAULT_SERVICE_POST

EI_DATABASE_HELP = """
Base de Datos en la cual funcionará la Facturación Electrónica"""
EI_ENVIRONMENT_HELP = """
Indicador del tipo de ambiente de Facturación Electrónica que se usará en
esta Base de Datos"""
SERVICE_URL_HELP = """URL de envio de Facturación Electrónica del Proveedor"""
SERVICE_URL_GET_HELP = """URL de Respuesta de Proveedor"""
SERVICE_URL_POST_HELP = """
URL de envio de Facturación Electrónica del Facturador"""
SOFTWARE_TOKEN_HELP = """Token de Proveedor Tecnológico"""
SOFTWARE_CODE_DIAN_HELP = """Codigo de software dado por la DIAN"""
EI_TMP_PATH_HELP = """Directorio local para archivos temporales"""
EI_AUTOMATIC_GENERATION_HELP = """
Enviar factura electrónica automáticamente al validar la factura"""
ATTACH_CUSTOMER_ORDER_HELP = """
Adjuntar en el correo la orden de compra del cliente"""
ATTACH_DELIVERY_NOTE_HELP = """Adjuntar documento de remisión de pedido"""
ATTACH_INVOICE_DOCS_HELP = """
Adjuntar documentos adicionales al pdf y xml adjuntos en la factura"""
AUTO_ACCEPTANCE_EMAIL_HELP = """Enviar correo de aceptación al cliente
una vez la factura haya quedado aceptada por la DIAN"""
EI_ID_CUSTOMIZATION_HELP = """
Tipo de Operación principal de facturación electrónica de la compañía"""
TRIBUTARY_OBLIGATIONS_HELP = """
Usadas en la construcción del XML AttachedDocument"""


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Basic config

    electronic_invoice = fields.Boolean(
        string='Activar Facturación Electrónica')
    ei_database = fields.Char(
        string='Base de Datos', default=lambda self: self.env.cr.dbname,
        required=True, help=EI_DATABASE_HELP)
    ei_environment = fields.Selection(
        string='Ambiente',
        selection=[
            ('production', u'Producción'), ('test', u'Habilitación')],
        default='test', required=True, help=EI_ENVIRONMENT_HELP)
    ei_software_operation = fields.Selection(
        string='Operación de Software',
        selection=[
            ('own', u'Software Propio'),
            ('provider', u'Proveedor Tecnológico')],
        default='provider', required=True)

    # Server

    service_url = fields.Char(
        string='URL Servicio', help=SERVICE_URL_HELP,
        default=DEFAULT_SERVICE_URL)
    service_url_get = fields.Char(
        string='URL Respuesta', help=SERVICE_URL_GET_HELP,
        default=DEFAULT_SERVICE_URL_GET)
    service_url_post = fields.Char(
        string='URL Peticion', help=SERVICE_URL_POST_HELP,
        default=DEFAULT_SERVICE_POST)
    software_token = fields.Char(
        string='Token', help=SOFTWARE_TOKEN_HELP)
    software_code_dian = fields.Char(
        string='Codigo Software DIAN', help=SOFTWARE_CODE_DIAN_HELP)
    ei_tmp_path = fields.Char(
        string='Ruta de Archivos Temporales',
        help=EI_TMP_PATH_HELP, default='/tmp')

    # Policies

    ei_automatic_generation = fields.Boolean(
        string='Enviar Factura al Validar',
        help=EI_AUTOMATIC_GENERATION_HELP)
    attach_customer_order = fields.Boolean(
        string='Adjuntar OC Cliente', help=ATTACH_CUSTOMER_ORDER_HELP)
    attach_delivery_note = fields.Boolean(
        string='Adjuntar Remisión', help=ATTACH_DELIVERY_NOTE_HELP)
    attach_invoice_docs = fields.Boolean(
        string='Envíar Adjuntos de Factura',
        help=ATTACH_INVOICE_DOCS_HELP)
    auto_acceptance_email = fields.Boolean(
        string='Email de Aceptación Automático',
        help=AUTO_ACCEPTANCE_EMAIL_HELP)

    # Settings

    ei_id_customization = fields.Selection(
        string='Operación Principal',
        selection=[('09', 'AIU'), ('10', 'Estandar'), ('11', 'Mandatos')],
        required=True, default='10',
        help=EI_ID_CUSTOMIZATION_HELP)
    mail_server_id = fields.Many2one(
        string='Servidor Email Preferido',
        comodel_name='ir.mail_server')
    ei_report_id = fields.Many2one(
        string='Formato PDF', comodel_name='ir.actions.report',
        domain=[('model', '=', 'account.move')])
    tributary_obligations = fields.Char(
        string='Obligaciones Tributarias',
        help=TRIBUTARY_OBLIGATIONS_HELP,
        default='R-99-PN')
    invoice_batch_process = fields.Boolean(string='Procesamiento Masivo')
