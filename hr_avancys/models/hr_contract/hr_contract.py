# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
from datetime import date
from datetime import datetime
from odoo.addons.avancys_tools.time import days360
from ..hr_payslip_period.hr_period import TYPE_PERIOD
from ..hr_contract.hr_contract_type import CONTRACT_TERM
from datetime import timedelta

CONTRACT_GROUP_ID_HELP = """
Este campo permite agrupar los contratos, según se va a calcular la nómina.
Sirve para grupos que no sea por banco, centro de costo y/o ciudad de desempeño.
"""
ARL_ID_HELP = "ARL en el caso que el empleado sea independiente"
ANALYTIC_DISTRIBUTION_TOTAL_WARN = """: La suma de las distribuciones analíticas debe ser 100.0%%,
Valor actual: %s%%"""
CONTRACT_EXTENSION_NO_RECORD_WARN = """
Para prorrogar el contrato por favor registre una prorroga
"""
CONTRACT_EXTENSION_MAX_WARN = """
No es posible realizar una prórroga por un periodo inferior
a un año despues de tener 3 o más prórrogas
"""
NO_PARTNER_REF_WARN = """
No se encontró el numero de documento en el contacto
"""
IN_FORCE_CONTRACT_WARN = """
El empleado yá tiene un contrato activo: %s.
"""

NO_WAGE_HISTORY = """
El contrato %s no tiene un historial de salarios.
"""

MANY_WAGE_HISTORY = """
El contrato %s tiene %s cambios salariales en este rango %s a %s.
Solo se permite 1 por periodo.
"""

LAST_ONE = -1

SETTLEMENT_TYPE_SELECTION = [
    ('vol', 'Retiro Voluntario del Trabajador'),
    ('lab', 'Terminación de la Labor Contratada'),
    ('causa', 'Cancelación por Justa Causa'),
    ('prueba', 'Terminación del Contrato en Periodo de Prueba'),
    ('n_causa', 'Retiro sin Justa Causa'),
    ('exp', 'Expiración Plazo Fijo Pactado'),
    ('unil', 'Decisión Unilateral de la Compañía'),
    ('fal', 'Fallecimiento'),
    ('pen', 'Pensionado'),
    ('nolab', 'No Laboró'),
    ('mutuo', 'Terminación Mutuo Acuerdo')
]


class HRContract(models.Model):
    _inherit = 'hr.contract'

    name = fields.Char(string='Contract Reference',
                       required=True, default='- NUEVO CONTRATO -')
    risk_id = fields.Many2one(string='Riesgo', comodel_name='hr.contract.risk')
    risk_percentage = fields.Float(
        string='Porcentaje de Riesgo', related='risk_id.risk_percentage', digits=(16, 6))
    high_risk = fields.Boolean(string='Alto Riesgo')
    contract_city_id = fields.Many2one(
        string='Ciudad de Contrato', comodel_name='res.city')
    work_city_id = fields.Many2one(
        string='Ciudad de Desempeño', comodel_name='res.city')
    contract_group_id = fields.Many2one(
        string='Grupo de Contrato', comodel_name='hr.contract.group',
        help=CONTRACT_GROUP_ID_HELP, tracking=True)
    contract_type_id = fields.Many2one(
        string='Tipo de Contrato', comodel_name='hr.contract.type',
        tracking=True)
    job_id = fields.Many2one(string='Título del Cargo', comodel_name='hr.job')
    term = fields.Selection(CONTRACT_TERM, 'Termino',
                            related="contract_type_id.term", store=True)
    eps_id = fields.Many2one(
        string='EPS', comodel_name='res.partner', domain="[('eps','=','True')]")
    eps_history_ids = fields.One2many(
        string='Histórico EPS', comodel_name='eps.update.history',
        inverse_name='contract_id')
    afp_pension_id = fields.Many2one(
        string='Fondo de Pensiones', comodel_name='res.partner', domain="[('afp','=','True')]")
    pension_history_ids = fields.One2many(
        string='Histórico Fondo de Pensiones', comodel_name='pension.update.history',
        inverse_name='contract_id')
    afp_severance_id = fields.Many2one(
        string='Fondo de Cesantías', comodel_name='res.partner', domain="[('afp','=','True')]")
    severance_history_ids = fields.One2many(
        string='Histórico Fondo de Cesantías', comodel_name='severance.update.history',
        inverse_name='contract_id')
    arl_id = fields.Many2one(
        string='ARL', comodel_name='res.partner',
        domain="[('arl','=','True')]", help=ARL_ID_HELP)
    ccf_id = fields.Many2one(
        string='CCF', comodel_name='res.partner',
        domain="[('ccf','=','True')]")

    # Salario y Beneficios

    wage_history_ids = fields.One2many(
        string='Histórico Salario', comodel_name='wage.update.history',
        inverse_name='contract_id')
    bonus = fields.Monetary(string='Bono')
    fiscal_type_id = fields.Many2one(
        string='Tipo de Cotizante', comodel_name='hr.fiscal.type',
        tracking=True)
    fiscal_subtype_id = fields.Many2one(
        string='Subtipo de Cotizante', comodel_name='hr.fiscal.subtype',
        tracking=True)
    skip_commute_allowance = fields.Boolean(
        string='Omitir Auxilio de Transporte')
    remote_work_allowance = fields.Boolean(
        string='Aplica Auxilio de Conectividad')
    minimum_wage = fields.Boolean(
        string='Devenga Salario Mínimo')
    limit_deductions = fields.Boolean(
        string='Limitar Deducciones al 50% de Devengos')
    workcenter = fields.Char(string='Centro de Trabajo')

    # Duración

    trial_date_start = fields.Date(string='Periodo de Prueba')
    trial_date_end = fields.Date(string='Fin de Periodo de Prueba')
    contract_days = fields.Integer(string='Días de Contrato')
    schedule_pay = fields.Selection(
        string='Categoría', selection=TYPE_PERIOD, default='MONTHLY', required=True)
    apprentice_to_worker_date = fields.Date(
        string='Fecha de Cambio a Etapa Productiva')

    # Liquidación

    settlement_date = fields.Date(string='Fecha de liquidación')
    settlement_period_id = fields.Many2one(
        string='Periodo de liquidación', comodel_name='hr.period')
    settlement_type = fields.Selection(
        string='Tipo de finalización', selection=SETTLEMENT_TYPE_SELECTION)

    # Deducciones

    deduction_dependents = fields.Boolean(string='Dependientes')
    deduction_by_estate = fields.Monetary(
        string='Deducción por Interes de Vivienda')
    deduction_by_healthcare = fields.Monetary(
        string='Deducción por Medicina Prepagada')
    deduction_by_icetex = fields.Monetary(
        string='Deducción por Intereses de ICETEX')

    # Contabilidad

    journal_id = fields.Many2one(
        string='Libro de Salarios', comodel_name='account.journal')
    analytic_distribution_ids = fields.One2many(
        string='Distribuciones Analíticas',
        comodel_name='hr.contract.analytic.distribution',
        inverse_name='contract_id')

    # Dotaciones

    equipment_ids = fields.One2many(
        string='Dotaciones', comodel_name='hr.equipment',
        inverse_name='contract_id')

    # Historial de Nominas

    paysplip_ids = fields.One2many(
        string='Historial de Nominas', comodel_name='hr.payslip',
        inverse_name='contract_id')

    # Procedimiento 2

    apply_procedure_2 = fields.Boolean(string='Aplicar Procedimiento 2')
    withholding_percent = fields.Float(string='Porcentaje de Retención')
    withholding_log_ids = fields.One2many(
        string='Calculo de Rete-Fuente Procedimiento 2',
        comodel_name='hr.contract.withholding.log', inverse_name='contract_id')

    # Prorrogas

    contract_extension_ids = fields.One2many(
        string='Prórrogas',
        comodel_name='hr.contract.extension', inverse_name='contract_id')

    # Libro de vacaciones

    holiday_book_ids = fields.One2many(
        comodel_name='hr.holiday.book', inverse_name='contract_id', string='Libro de vacaciones')
    days_left = fields.Float(string='Días restantes', default=0, readonly=True)
    date_ref_holiday_book = fields.Date(string='Fecha referencia')

    def _get_contract_name(self, employee_id):
        contracts = self.env['hr.contract'].search([
            ('employee_id', '=', employee_id)
        ])
        employee = self.env['hr.employee'].browse([employee_id])
        ref_num = employee.partner_id.ref_num
        if not ref_num:
            raise ValidationError(NO_PARTNER_REF_WARN)
        contract_number = 'C' + str(len(contracts) + 1).rjust(2, '0')
        return ref_num + ' - ' + contract_number

    @api.model
    def create(self, vals):
        employee_id = vals.get('employee_id', False)
        vals['name'] = self._get_contract_name(employee_id)
        contracts = self.env['hr.contract'].search([
            ('employee_id', '=', employee_id)
        ])
        in_force_contracts = contracts.filtered(
            lambda contract: (not contract.date_end) or contract.date_end > date.today())
        if in_force_contracts:
            raise ValidationError(
                IN_FORCE_CONTRACT_WARN % in_force_contracts[0].name)
        return super(HRContract, self).create(vals)

    @api.onchange('eps_history_ids', 'pension_history_ids', 'severance_history_ids')
    @api.constrains('eps_history_ids', 'pension_history_ids', 'severance_history_ids')
    def _update_social_security_from_history(self):
        for contract in self:
            if contract.eps_history_ids:
                contract.eps_id = contract.eps_history_ids.sorted(
                    lambda hist: hist.date)[LAST_ONE].eps_id
            if contract.pension_history_ids:
                contract.afp_pension_id = contract.pension_history_ids.sorted(
                    lambda hist: hist.date)[LAST_ONE].afp_pension_id
            if contract.severance_history_ids:
                contract.afp_severance_id = contract.severance_history_ids.sorted(
                    lambda hist: hist.date)[LAST_ONE].afp_severance_id

    @api.onchange('wage_history_ids')
    @api.constrains('wage_history_ids')
    def _update_wage_from_history(self):
        for contract in self:
            if contract.wage_history_ids:
                contract.wage = contract.wage_history_ids.sorted(
                    lambda hist: hist.date)[LAST_ONE].wage

    @api.constrains('date_start')
    def _compute_trial_period(self):
        trial_months = 2
        trial_time = relativedelta(months=trial_months) - relativedelta(days=1)
        for contract in self:
            contract.trial_date_start = contract.date_start
            contract.trial_date_end = contract.date_start + trial_time

    @api.constrains('analytic_distribution_ids')
    def _check_analytic_distribution_sum(self):
        for contract in self:
            total = sum(
                [adst.rate for adst in contract.analytic_distribution_ids])
            if 0.0 != total != 100.0:
                raise ValidationError(contract.name +
                                      ANALYTIC_DISTRIBUTION_TOTAL_WARN % total)

    def extend_contract(self):
        """Extend contract end date"""
        max_extensions, min_days = 3, 360
        for contract in self:
            if not contract.contract_extension_ids:
                raise ValidationError(CONTRACT_EXTENSION_NO_RECORD_WARN)
            last_extension = contract.contract_extension_ids.sorted(
                key=lambda r: r.sequence)[LAST_ONE]
            contract.date_end = last_extension.date_to
            if len(contract.contract_extension_ids) <= max_extensions:
                continue
            extension_span_days = days360(
                last_extension.date_from, last_extension.date_to)
            if extension_span_days < min_days:
                raise ValidationError(CONTRACT_EXTENSION_MAX_WARN)

    def get_wage(self, date_end, date_start=False):
        """
        Obtiene el salario en determinada fecha
        @return:
            dict -> {fecha, salario, salario_anterior}
        """
        if not self.wage_history_ids:
            raise ValidationError(NO_WAGE_HISTORY % self.name)
        if date_start:
            salary = list(filter(
                lambda x: date_start <= x.date <= date_end, self.wage_history_ids))
            if not salary:
                return self.get_wage(date_end)
            elif len(salary) > 1:
                raise ValidationError(MANY_WAGE_HISTORY % (
                    self.name, len(salary), date_start, date_end))
            elif date_start <= self.date_start <= date_end:
                return {'wage': salary[0].wage}
            last = self.get_wage(salary[0].date - timedelta(days=1))
            return {'date': salary[0].date, 'wage': salary[0].wage, 'last_wage': last['wage']}
        salary = list(filter(
            lambda x: x.date <= date_end, self.wage_history_ids))
        if not salary:
            raise ValidationError(
                (NO_WAGE_HISTORY + 'Para esta fecha %s') % (self.name, date_end))
        salary = max(salary, key=lambda x: x.date)
        return {'wage': salary.wage}

    def get_holiday_book(self, date_ref=False):
        date_ref = date_ref or self.date_ref_holiday_book or datetime.now()
        worked_days = days360(self.date_start, date_ref)
        days_enjoyed, days_paid, days_suspension = 0, 0, 0
        for holiday_book in self.holiday_book_ids:
            days_enjoyed += holiday_book.days_enjoyed
            days_paid += holiday_book.days_paid
            days_suspension += holiday_book.days_suspension
        worked_days -= days_suspension
        days_left = (worked_days * 15 / 360) - (days_enjoyed + days_paid)
        return {
            'worked_days': worked_days,
            'days_left': days_left,
            'days_enjoyed': days_enjoyed,
            'days_paid': days_paid,
            'days_suspension': days_suspension,
        }

    def update_days_left(self):
        self.days_left = self.get_holiday_book()['days_left']

    def liquidate_contract(self):
        payslips_liq = []
        payslip_type = self.env['hr.payslip.type'].search(
            [('category', '=', 'LIQ')], limit=1)
        if not payslip_type:
            raise ValidationError(
                'No se encontró la categoría de nómina de categoría liquidación.')
        for record in self:
            message = 'El contrato %s no tiene ' % record.name
            if record.state != 'open':
                continue
            elif not record.settlement_date:
                raise ValidationError(message + 'fecha de liquidación.')
            elif not record.settlement_period_id:
                raise ValidationError(message + 'periodo de liquidación.')
            elif not record.settlement_type:
                raise ValidationError(message + 'tipo de finalización.')
            payslips_liq.append({
                'state': 'draft',
                'contract_id': record.id,
                'liquidation_date': record.settlement_date,
                'accounting_date': record.settlement_date,
                'company_id': self.env.company.id,
                'period_id': record.settlement_period_id.id,
                'payslip_type_id': payslip_type.id,
            })
        payslips_liq_ids = self.env['hr.payslip'].create(payslips_liq)
        payslips_liq_ids.compute_slip(self._cr)
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'hr.payslip',
            'target': 'current',
            'context': {},
            'domain': [('id', 'in', payslips_liq_ids.ids)],
        }
