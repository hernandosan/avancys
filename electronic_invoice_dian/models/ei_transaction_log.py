# -*- coding: utf-8 -*-

from openerp import models, fields, api

DOCUMENT_STATE_SELECTION = [
    ('sent', 'Emitido'),
    ('dian_reject', 'Rechazo Dian'),
    ('dian_accept', 'Aceptación Dian'),
    ('email_sent', 'Email Enviado'),
    ('email_fail', 'Email Fallido'),
    ('customer_accept', 'Aceptación Cliente'),
    ('customer_reject', 'Rechazo Cliente'),
    ('provider_error', 'Error de Procesamiento'),
    ('exception', 'Excepción de Envio'),
]
DOCUMENT_TYPE_SELECTION = [
    ('json', 'Json'),
    ('app_response', 'Application Response'),
    ('xml_fe', 'Factura XML'),
    ('none', 'Ninguno'),
]


class EITransactionLog(models.Model):
    _name = 'ei.transaction.log'
    _description = 'Log de Facturacion Electronica'
    _order = 'date desc'

    invoice_id = fields.Many2one(
        string='Factura', comodel_name='account.move', readonly=True)
    date = fields.Datetime(string='Fecha', readonly=True)
    document_state = fields.Selection(
        string='Estado', selection=DOCUMENT_STATE_SELECTION, readonly=True)
    document_type = fields.Selection(
        string='Tipo de documento', selection=DOCUMENT_TYPE_SELECTION,
        readonly=True)
    content = fields.Text(string='Contenido', readonly=True)
