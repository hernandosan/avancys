# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

MODALITY = [
    ('EXT', 'Exento de retención'),
    ('AVP', 'Aporte voluntario de pensión'),
    ('AFC', 'Ahorro y fomento a la construcción')
]


class HrNoveltyType(models.Model):
    _name = 'hr.novelty.type'
    _inherit = 'model.basic.payslip.novelty.type'
    _description = 'Categoría de Novedades'
    _order = 'name'

    dep_days_worked = fields.Boolean(
        string='Depende de días trabajados', default=False)
    modality = fields.Selection(
        string='Modalidad de retención', selection=MODALITY, default=False)
