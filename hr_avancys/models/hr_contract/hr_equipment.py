# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HREquipment(models.Model):
    _name = 'hr.equipment'
    _description = 'Dotación de RRHH'

    name = fields.Char(string='Nombre', required=True)
    product_id = fields.Many2one(
        string='Producto', comodel_name='product.product', required=True)
    product_lot_id = fields.Many2one(
        string='Serial', comodel_name='stock.production.lot')
    amount_info = fields.Char(string='Cantidad/Informacion', required=True)
    contract_id = fields.Many2one(
        string='Contrato', comodel_name='hr.contract')
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.company,
        index=True, required=True)
