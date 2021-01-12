# -*- coding: utf-8 -*-
from openerp import models, fields, api

EI_CODE_SELECTION = [
    ('01', 'IVA'),
    ('02', 'IC'),
    ('03', 'ICA'),
    ('04', 'INC'),
    ('05', 'ReteIVA'),
    ('06', 'ReteFuente'),
    ('07', 'ReteICA')
]


class AccountTax(models.Model):
    _inherit = 'account.tax'

    ei_code = fields.Selection(
        string='Código Facturación Electrónica',
        selection=EI_CODE_SELECTION)
