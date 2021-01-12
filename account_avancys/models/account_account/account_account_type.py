# -*- coding: utf-8 -*-
from odoo import api, fields, models


class AccountAccountType(models.Model):
    _inherit = 'account.account.type'

    type = fields.Selection([
        ('view','Vista'),
        ('other', 'Regular'),
        ('receivable', 'Receivable'),
        ('payable', 'Payable'),
        ('liquidity', 'Liquidity'),
        ('consolidation','Consolidación'),
        ('closed','Cerrado'),
    ])