# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

INVALID_TYPE_WARN = """Tipo de diario no válido para facturación electrónica"""


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    resolution_id = fields.Many2one(
        string='Resolución de Numeración',
        comodel_name='electronic.invoice.resolution')

    @api.constrains('resolution_id')
    def check_document_type(self):
        if self.type != 'sale' and self.resolution_id:
            raise ValidationError(INVALID_TYPE_WARN)
