# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    ciiu_id = fields.Many2one(
        comodel_name='res.ciiu', 
        string='CIIU'
    )
    property_account_advance_customer_id = fields.Many2one(
        company_dependent=True,
        comodel_name='account.account',
        string='Cuenta Anticipo Cliente',
    )
    property_account_advance_supplier_id = fields.Many2one(
        company_dependent=True,
        comodel_name='account.account',
        string='Cuenta Anticipo Proveedor',
    )
