# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

STATE = [
    ('draft', 'Borrador'),
    ('confirm', 'Confirmada'),
    ('validated', 'Validada'),
    ('cancel', 'Canelado'),
    ('paid', 'Pagada')
]


class ModelBasicPayslipNovelty(models.AbstractModel):
    _name = 'model.basic.payslip.novelty'
    _description = 'model.basic.payslip.novelty'
    _order = 'name'

    name = fields.Char(string='Nombre', readonly=True)
    state = fields.Selection(string='Estado', selection=STATE, default='draft')
    contract_id = fields.Many2one(comodel_name='hr.contract', string='Contrato',
                                  domain="[('state','=','open')]", required=True)
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Empleado',
                                  compute='_compute_employee', inverse='_inverse_get_contract')
    approve_date = fields.Date(string='Fecha de aprobación')
    date_start = fields.Date(string='Fecha Inicio', required=True)
    date_end = fields.Date(string='Fecha Final')
    amount = fields.Float(string='Valor')
    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company, readonly=True)

    @api.depends('contract_id')
    def _compute_employee(self):
        for record in self:
            if record.contract_id:
                if not record.contract_id.employee_id:
                    raise ValidationError(
                        'El contrato %s no tiene un emplado relacionado' % self.contract_id.name)
                record.employee_id = record.contract_id.employee_id
            else:
                record.employee_id = False

    def _inverse_get_contract(self):
        for record in self:
            contract_id = self.env['hr.contract'].search(
                [('employee_id', '=', record.employee_id.id), ('state', '=', 'open')])
            if not contract_id:
                raise ValidationError(
                    'El emplado %s no tiene contrato en proceso' % (record.employee_id.name))
            if len(contract_id) > 1:
                raise ValidationError('El emplado %s tiene %s contratos en proceso' % (
                    record.employee_id.name, len(contract_id)))
            record.contract_id = contract_id

    def to_cancel(self):
        for record in self:
            if record.state != 'paid':
                record.state = 'cancel'

    def to_draft(self):
        for record in self:
            if record.state != 'paid':
                record.state = 'draft'

    def to_confirm(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'confirm'

    def to_validated(self):
        for record in self:
            if record.state == 'confirm':
                record.state = 'validated'
