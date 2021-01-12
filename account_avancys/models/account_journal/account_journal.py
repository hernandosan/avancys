# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    default_account_id = fields.Many2one(
        comodel_name='account.account', 
        check_company=True, 
        copy=False, 
        ondelete='restrict',
        string='Cuenta Por Defecto',
        domain=[]
    )
     