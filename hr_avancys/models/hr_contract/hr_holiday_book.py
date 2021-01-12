# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrHolidayBook(models.Model):
    _name = 'hr.holiday.book'
    _description = 'Libro de vacaciones'

    contract_id = fields.Many2one(
        comodel_name='hr.contract', string='Contrato', required=True)
    leave_id = fields.Many2one(
        comodel_name='hr.leave', string='Ausencia', required=True)
    payslip_id = fields.Many2one(
        comodel_name='hr.payslip', string='Nónima', required=True)
    days_enjoyed = fields.Integer(string='Días disfrutados', default=0)
    days_paid = fields.Integer(string='Días pagados', default=0)
    days_suspension = fields.Integer(string='Días de suspensiones', default=0)
    initial_balance = fields.Boolean(string='Saldo inicial', default=False)
