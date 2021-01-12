# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

YEARS = [(str(x), str(x))
         for x in range(datetime.now().year - 5, datetime.now().year + 6)]


class EconomicVariablesLine(models.Model):
    _name = 'economic.variable.line'
    _description = 'Línea de variable económica'
    _order = 'id'

    variable_id = fields.Many2one(
        comodel_name='economic.variable', string='Variable económica')
    year = fields.Selection(string='Año', selection=YEARS)
    value = fields.Float(string='Valor')
    compute_value = fields.Boolean(
        string='Valor calculado', help="Aplica principalmente para la tabla de retención en la fuente",
        related="variable_id.compute_value")
    variable_line_detail_ids = fields.One2many(
        comodel_name='economic.variable.line.detail', inverse_name='variable_line_id',
        string='Detalles de línea de variable económica')

    _sql_constraints = [
        ("line_uniq", "unique (variable_id, year)",
         "Ya está definido un valor para esta variable económica en el año especificado.")
    ]
