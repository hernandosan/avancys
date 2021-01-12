# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountFiscalPositionTax(models.Model):
    _inherit = 'account.fiscal.position.tax'

    value = fields.Float(string='Valor')
    option = fields.Selection([('always','Siempre'), 
                               ('great','>'), 
                               ('great_equal','>='), 
                               ('equal','='), 
                               ('minor','<'), 
                               ('minor_equal','<=')], string='Opción', required=True)