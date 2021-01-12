# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResCiiu(models.Model):
    _name = 'res.ciiu'

    name = fields.Char(string='Código', size=4, required=True)
    description = fields.Char(string='Descripción', required=True)
    tax_ids = fields.Many2many('account.tax', 'res_ciiu_tax_rel', 'ciiu_id', 'tax_id', string='Impuestos')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', '¡El Nombre tiene que ser unico!'),
    ]
