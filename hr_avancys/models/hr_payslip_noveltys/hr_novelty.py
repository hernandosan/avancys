# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

TYPE_NOVELTY = [
    ('RECURRENT', 'Recurrente'),
    ('STATIC', 'Estatica')
]


class HrNovelty(models.Model):
    _name = 'hr.novelty'
    _inherit = 'model.basic.payslip.novelty'
    _description = 'Novedad'
    _order = 'name'

    type_novelty = fields.Selection(
        string='Tipo', selection=TYPE_NOVELTY, default='STATIC', required=True)
    novelty_type_id = fields.Many2one(
        comodel_name='hr.novelty.type', string='Categoría de Novedad', required=True)
    novelty_line_ids = fields.One2many(
        comodel_name='hr.novelty.line', inverse_name='novelty_id', readonly=True, string='Lineas de Novedad')

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code(
            'seq.hr.novelty') or ''
        return super(HrNovelty, self).create(vals)

    def to_validated(self):
        period = self.env['hr.period']
        for record in self:
            if record.state != 'confirm':
                continue
            periods = period.get_period(
                record.date_start,
                record.date_end if record.type_novelty == 'RECURRENT' else False, record.contract_id.schedule_pay)
            record.novelty_line_ids = record._prepare_novelty_line(periods.ids)
        return super(HrNovelty, self).to_validated()

    def to_draft(self):
        for record in self:
            if record.state != 'validated':
                continue
            record.novelty_line_ids.unlink()
        return super(HrNovelty, self).to_draft()

    def _prepare_novelty_line(self, periods):
        """funtion per record"""
        new_novelty_line = []
        for period in periods:
            new_novelty_line.append((0, 0, {
                'period_id': period,
                'state': 'validated',
                'amount': self.amount,
            }))
        return new_novelty_line

    def to_paid(self):
        for record in self:
            paid = True
            for novelty_line in record.novelty_line_ids:
                paid &= novelty_line.state == 'paid'
            if paid:
                record.state = 'paid'

    def to_cancel(self):
        for record in self:
            if record.state == 'validated':
                record.novelty_line_ids.unlink()
        return super(HrNovelty, self).to_cancel()
