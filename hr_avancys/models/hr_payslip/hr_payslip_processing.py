# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.addons.avancys_tools import orm
from ..hr_payslip_period.hr_period import TYPE_PERIOD

STATE = [
    ('draft', 'Borrador'),
    ('paid', 'Pagada')
]


class HrPayslipProcessing(models.Model):
    _name = 'hr.payslip.processing'
    _description = 'Procesamiento de Nómina'
    _order = 'name'

    name = fields.Char(string='Nombre', readonly=True,
                       compute="_get_name", store=True)
    state = fields.Selection(string='Estado', selection=STATE, default='draft')
    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company, readonly=True)
    period_id = fields.Many2one(
        comodel_name='hr.period', string='Periodo',
        domain=[('active', '=', True)], required=True)
    type_period = fields.Selection(
        string='Tipo de periodo', selection=TYPE_PERIOD,
        readonly=True, related='period_id.type_period')
    liquidation_date = fields.Date(
        string='Fecha de Liquidación', required=True)
    accounting_date = fields.Date(
        string='Fecha de Contabilización', required=True)
    payslip_type_id = fields.Many2one(
        comodel_name='hr.payslip.type', string='Tipo de Nómina',
        required=True)
    contract_group_id = fields.Many2one(
        comodel_name='hr.contract.group', string='Grupo de Contrato')

    contracts_ids = fields.Many2many(
        comodel_name='hr.contract', string='Contratos',
        relation='hr_payslip_processing_hr_contract_rel',
        copy=False)
    payslips_ids = fields.One2many(
        comodel_name='hr.payslip', string='Nóminas',
        inverse_name='payslip_processing_id', copy=False)
    error_log = fields.Text(string='Errores', readonly=True)

    @api.depends('period_id', 'payslip_type_id', 'contract_group_id')
    def _get_name(self):
        fields_eval = ['period_id', 'payslip_type_id', 'contract_group_id']
        total = len(fields_eval) - 1
        for record in self:
            name = ''
            for i, fe in enumerate(fields_eval):
                name_tmp = getattr(self, fe).name
                name += name_tmp + ' - ' if name_tmp else ''
            if len(name) > 3 and name[-3:] == ' - ':
                record.name = name[:-3]
            else:
                record.name = name

    def load_contracts_ids(self):
        add_contract = []
        for record in self:
            param = {
                'period_id': record.period_id.id,
                'type_period': record.type_period,
                'payslip_type_id': record.payslip_type_id.id,
            }
            if record.contract_group_id:
                filter_contract_group_id = "AND contract_group_id = %(contract_group_id)s"
                param['contract_group_id'] = record.contract_group_id.id
            else:
                filter_contract_group_id = ''
            contracts_ids_sel = """
            SELECT HC.id FROM hr_contract as HC
            LEFT JOIN (
                SELECT HPPHC.hr_contract_id AS id
                FROM hr_payslip_processing_hr_contract_rel as HPPHC
                INNER JOIN hr_payslip_processing HPP
                    ON HPP.id = HPPHC.hr_payslip_processing_id
                WHERE
                    HPP.period_id = %(period_id)s AND
                    HPP.payslip_type_id = %(payslip_type_id)s
            ) as HCP ON HCP.id = HC.id
            WHERE
                HCP.id IS NULL AND HC.state = 'open' AND
                HC.schedule_pay = %(type_period)s {fcg}
            """.format(fcg=filter_contract_group_id)
            contracts_ids = orm.fetchall(self._cr, contracts_ids_sel, param)
            for contract_id in contracts_ids:
                add_contract.append({
                    'hr_payslip_processing_id': record.id,
                    'hr_contract_id': contract_id[0],
                })
        orm.create(self._cr, self.env.uid,
                   'hr_payslip_processing_hr_contract_rel', add_contract, progress=True)

    def create_payslips_ids(self):
        new_payslip = []
        seq_id, prefix, padding, suffix = orm.fetchall(
            self._cr, "SELECT id, prefix, padding, suffix FROM ir_sequence where code = %s", ['seq.hr.payslip'])[0]
        number = orm.fetchall(self._cr, "SELECT nextval(%s)",
                              ["ir_sequence_%03d" % seq_id])[0][0]
        for record in self:
            contracts_no_payslip_sel = """
            SELECT HPPHC.hr_contract_id
            FROM hr_payslip_processing_hr_contract_rel as HPPHC
            LEFT JOIN hr_payslip as HP
                ON  HP.contract_id = HPPHC.hr_contract_id AND
                    HP.period_id = %(period_id)s AND
                    HP.payslip_type_id = %(payslip_type_id)s
            WHERE
                HP.id IS NULL AND
                HPPHC.hr_payslip_processing_id = %(processing)s
            """
            contracts_no_payslip = orm.fetchall(self._cr, contracts_no_payslip_sel, {
                'period_id': record.period_id.id,
                'payslip_type_id': record.payslip_type_id.id,
                'processing': record.id
            })
            if not contracts_no_payslip:
                continue
            for cnp in contracts_no_payslip:
                new_payslip.append({
                    'name': f"{prefix if prefix else ''}{number:0{padding}}{suffix if suffix else ''}",
                    'state': 'draft',
                    'contract_id': cnp[0],
                    'liquidation_date': record.liquidation_date,
                    'accounting_date': record.accounting_date,
                    'company_id': self.env.company.id,
                    'period_id': record.period_id.id,
                    'payslip_type_id': record.payslip_type_id.id,
                    'payslip_processing_id': record.id,
                })
                number += 1

        orm.create(self._cr, self.env.uid, 'hr_payslip',
                   new_payslip, progress=True)
        orm.restart_sequence(self._cr, "ir_sequence_%03d" % seq_id, number)

    def compute_payslips_ids(self):
        payslips_ids = []
        for record in self:
            for payslip in record.payslips_ids:
                if payslip.period_id.id != record.period_id.id or \
                        payslip.payslip_type_id.id != record.payslip_type_id.id:
                    raise ValidationError(
                        'Las nómina del procesamiento de nómina deben tener el mismo periodo y mismo tipo de nómina')
            record.error_log = record.payslips_ids.compute_slip()

    def drop_payslips_ids(self):
        payslip_delete = []
        for record in self:
            payslip_delete += record.payslips_ids.ids
        self.env['hr.payslip'].browse(payslip_delete).unlink()

    def unlink_contracts_ids(self):
        for record in self:
            record.contracts_ids = [(5, 0, 0)]
