# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

DATASIZE_RATIO = 3.0 / 4.0  # converts from len to actual filesize
MAX_FILE_SIZE = 2000000
MAX_SIZE_WARN = """
El tamaño del archivo de la Orden de Compra Cliente supera los 2Mb permitidos"""


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    customer_po_file = fields.Binary(
        string='Orden de Compra Cliente', copy=False)
    customer_po_name = fields.Char('Nombre OC Cliente', copy=False)
    customer_po_policy = fields.Boolean(
        string='Política Envío OC', related='company_id.attach_customer_order',
        readonly=True)

    @api.constrains('customer_po_file')
    def _check_file_size(self):
        if len(self.customer_po_file) * DATASIZE_RATIO > MAX_FILE_SIZE:
            raise ValidationError(MAX_SIZE_WARN)
