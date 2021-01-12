# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountTax(models.Model):
    _inherit = 'account.tax'

    child_cities_ids = fields.One2many('account.tax', 'parent_city_id', string='Impuestos Ciudades Hijas')
    parent_city_id = fields.Many2one('account.tax', string='Impuesto Ciudades Padre')
    city_id = fields.Many2one('res.city', string='Ciudad')
    ciiu_ids = fields.Many2many('res.ciiu', 'tax_ciiu_rel', 'tax_id', 'ciiu_id', string='CIIU asociados')
    check_lines = fields.Boolean(string='Impuesto ICA')
