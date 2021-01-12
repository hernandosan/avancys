# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from ..hr_payslip_noveltys.model_basic_payslip_novelty_type import CATEGORY_PAYSLIP

ORIGIN = [
    ('local', 'Local'),
    ('import', 'Importación')
]


class HrPayslipLine(models.Model):
    _name = 'hr.payslip.line'
    _description = 'Linea de Nómina'
    _order = 'name'

    name = fields.Char(string='Nombre')
    payslip_id = fields.Many2one(
        comodel_name='hr.payslip', string='Nómina', required=True)
    category = fields.Selection(string='Categoría', selection=CATEGORY_PAYSLIP)
    value = fields.Float(string='Valor')
    qty = fields.Float(string='Cantidad')
    rate = fields.Float(string='Porcentaje')
    total = fields.Float(string='Total')
    origin = fields.Selection(string='Origen', selection=ORIGIN)
    concept_id = fields.Many2one(
        comodel_name='hr.concept', string='Concepto')
    leave_id = fields.Many2one(
        comodel_name='hr.leave', string='Ausencia')
    novelty_id = fields.Many2one(
        comodel_name='hr.novelty', string='Novedad')
    overtime_id = fields.Many2one(
        comodel_name='hr.overtime', string='Hora Extra')
