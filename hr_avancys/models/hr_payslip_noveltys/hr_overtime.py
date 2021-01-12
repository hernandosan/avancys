# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class HrOvertime(models.Model):
    _name = 'hr.overtime'
    _inherit = 'model.basic.payslip.novelty'
    _description = 'Hora Extra'
    _order = 'name'

    overtime_type_id = fields.Many2one(
        comodel_name='hr.overtime.type', string='Categoría Hora Extra', required=True)
    qty = fields.Float(string='Cantidad', required=True)
    payslip_id = fields.Many2one(
        comodel_name='hr.payslip', string='Nónima', readonly=True)
    period_id = fields.Many2one(
        comodel_name='hr.period', string='Periodo', readonly=True)
    amount = fields.Float(string='Valor', compute="_compute_value", store=True)
    rate = fields.Float(string='Factor', related='overtime_type_id.rate')

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code(
            'seq.hr.overtime') or ''
        return super(HrOvertime, self).create(vals)

    @api.depends('qty', 'rate', 'contract_id')
    def _compute_value(self):
        for record in self:
            if record.qty and record.overtime_type_id and record.contract_id:
                record.amount = record.qty * record.overtime_type_id.rate * \
                    record.contract_id.wage / 240

    def to_validated(self):
        period = self.env['hr.period']
        for record in self:
            if record.state != 'confirm':
                continue
            if not record.contract_id:
                raise ValidationError(
                    "Por favor defina el contrato de la hora extra")
            if not record.date_start:
                raise ValidationError(
                    "Por favor defina la fecha de la hora extra")
            record.period_id = period.get_period(
                record.date_start, False, record.contract_id.schedule_pay)
        return super(HrOvertime, self).to_validated()

    def create_payslip_line(self, payslip_id):
        overtime_type_id = self.overtime_type_id
        payslip_line = {
            'name': overtime_type_id.name,
            'payslip_id': payslip_id,
            'category': overtime_type_id.category,
            'value': self.amount,
            'qty': 1,
            'rate': 100,
            'total': self.amount,
            'origin': 'local',
            'concept_id': None,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': self.id,
        }
        for unique_key in ['rate', 'concept_id', 'leave_id', 'novelty_id', 'overtime_id']:
            if 'unique_key' in payslip_line:
                payslip_line['unique_key'] += str(payslip_line[unique_key])
            else:
                payslip_line['unique_key'] = str(payslip_line[unique_key])
        return payslip_line

    def belongs_category(self, categories):
        return self.overtime_type_id.id in categories
