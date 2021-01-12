# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from odoo.addons.avancys_tools import orm
from .hr_concept import CONCEPTS, TPCT, TPCP, NCI
from datetime import timedelta
from calendar import monthrange

STATE = [
    ('draft', 'Borrador'),
    ('paid', 'Pagada')
]

CATEGORIES_SEARCH = ['earnings', 'o_salarial_earnings', 'comp_earnings',
                     'o_rights', 'o_earnings', 'deductions']

CONCEPTS_SEARCH = ['PRIMA', 'PRIMA_LIQ', 'DED_PENS',
                   'DED_EPS', 'FOND_SOL', 'FOND_SUB', 'RTEFTE']


class HrPayslip(models.Model):
    _name = 'hr.payslip'
    _description = 'Nómina'
    _order = 'name'

    name = fields.Char(string='Nombre', readonly=True)
    state = fields.Selection(string='Estado', selection=STATE, default='draft')
    contract_id = fields.Many2one(comodel_name='hr.contract', string='Contrato',
                                  domain="[('state','=','open')]", required=True)
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Empleado',
                                  compute='_compute_employee', inverse='_inverse_get_contract')
    liquidation_date = fields.Date(string='Fecha de Liquidación')
    accounting_date = fields.Date(string='Fecha de Contabilización')
    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company)
    period_id = fields.Many2one(
        comodel_name='hr.period', string='Periodo', domain=[('active', '=', True)])
    payslip_type_id = fields.Many2one(
        comodel_name='hr.payslip.type', string='Tipo de Nómina')
    payslip_day_ids = fields.One2many(
        comodel_name='hr.payslip.day', inverse_name='payslip_id', string='Días de Nómina', readonly=True)

    payslip_line_ids = fields.One2many(
        comodel_name='hr.payslip.line', inverse_name='payslip_id', string='Conceptos de Nómina')
    earnings_ids = fields.One2many(
        comodel_name='hr.payslip.line', compute="_compute_concepts_category", string='Conceptos de Nómina')
    deductions_ids = fields.One2many(
        comodel_name='hr.payslip.line', compute="_compute_concepts_category", string='Conceptos de Nómina')
    outcome_ids = fields.One2many(
        comodel_name='hr.payslip.line', compute="_compute_concepts_category", string='Conceptos de Nómina')

    payslip_processing_id = fields.Many2one(
        comodel_name='hr.payslip.processing', string='Procesamiento de Nómina')
    error_log = fields.Text(string='Errores', readonly=True)

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code(
            'seq.hr.payslip') or ''
        return super(HrPayslip, self).create(vals)

    def unlink(self):
        payslip_remove = [x.id for x in self if x.state == 'draft']
        orm.delete(self._cr, self.env.uid,
                   'hr.payslip.line', {'payslip_id': payslip_remove})
        orm.delete(self._cr, self.env.uid,
                   'hr.payslip.day', {'payslip_id': payslip_remove})
        orm.delete(self._cr, self.env.uid,
                   'hr.payslip', {'id': payslip_remove})

    @api.depends('payslip_line_ids')
    def _compute_concepts_category(self):
        for record in self:
            earnings = []
            deductions = []
            outcome = []
            for payslip_line in record.payslip_line_ids:
                if payslip_line.category in ['earnings', 'o_salarial_earnings', 'comp_earnings',
                                             'o_rights', 'o_earnings', 'non_taxed_earnings']:
                    earnings.append(payslip_line.id)
                elif payslip_line.category == 'deductions':
                    deductions.append(payslip_line.id)
                else:
                    outcome.append(payslip_line.id)
            record.earnings_ids = self.env['hr.payslip.line'].browse(
                earnings)
            record.deductions_ids = self.env['hr.payslip.line'].browse(
                deductions)
            record.outcome_ids = self.env['hr.payslip.line'].browse(
                outcome)

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

    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        res = {
            'value': {
                'period_id': False,
            },
            'domain': {
                'period_id': [('type_period', '=', self.contract_id.schedule_pay), ('active', '=', True)],
            },
        }
        return res

    def _get_politics(self):
        model = 'ir.config_parameter'
        politics = {
            'hr_avancys.pays_sub_trans_train_prod': bool,
            'hr_avancys.eps_rate_employee': float,
            'hr_avancys.pen_rate_employee': float,
            'hr_avancys.discount_suspensions': bool,
            'hr_avancys.average_sub_trans': bool,
            # 'hr_avancys.pen_rate_employer': float,
            # 'hr_avancys.eps_rate_employer': float,
        }
        for param in politics:
            politics[param] = (politics[param])(
                self.env[model].sudo().get_param(param))
        return politics

    def _check_concepts_belonging(self, concepts):
        compute = False
        blacklits = []
        for record in self:
            if record.payslip_type_id.id in blacklits:
                continue
            blacklits.append(record.payslip_type_id.id)
            for concept in record.payslip_type_id.concepts_ids:
                if concept.code in concepts:
                    compute = True
                    break
        return compute

    def _get_categories_search(self, total_previous, start, end):
        concepts_eval = ['IBD', 'DED_PENS', 'DED_EPS',
                         'FOND_SOL', 'FOND_SUB', 'BRTF', 'RTEFTE']
        if not self._check_concepts_belonging(concepts_eval):
            return
        param = {
            'categories': tuple(CATEGORIES_SEARCH),
            'contracts': tuple([x.contract_id.id for x in self]),
            'payslips': tuple(self.ids),
            'start': start,
            'end': end,
        }
        query = """
        SELECT HP.contract_id, HPL.category, sum(HPL.total)
        FROM hr_payslip_line as HPL
        INNER JOIN hr_payslip as HP
            ON HP.id = HPL.payslip_id
        INNER JOIN hr_period as PP
            ON PP.id = HP.period_id
        WHERE
            HP.state = 'paid' AND
            HPL.category IN %(categories)s AND
            PP.end > %(start)s AND
            PP.start < %(end)s AND
            HP.contract_id IN %(contracts)s AND
            HPL.payslip_id NOT IN %(payslips)s
        GROUP BY HP.contract_id, HPL.category
        """
        data = orm.fetchall(self._cr, query, param)
        for d in data:
            if d[0] not in total_previous:
                total_previous[d[0]] = {d[1]: d[2]}
            elif d[1] not in total_previous[d[0]]:
                total_previous[d[0]][d[1]] = d[2]
            else:
                total_previous[d[0]][d[1]] += d[2]

    def _get_concepts_search(self, total_concepts, start, end):
        if not self._check_concepts_belonging(CONCEPTS_SEARCH):
            return
        param = {
            'code': tuple(CONCEPTS_SEARCH),
            'contracts': tuple([x.contract_id.id for x in self]),
            'payslips': tuple(self.ids),
            'start': start,
            'end': end,
        }
        query = """
        SELECT HP.contract_id, HC.code, sum(HPL.total)
        FROM hr_payslip_line as HPL
        INNER JOIN hr_payslip as HP
            ON HP.id = HPL.payslip_id
        INNER JOIN hr_period as PP
            ON PP.id = HP.period_id
        INNER JOIN hr_concept as HC
            ON HC.id = HPL.concept_id
        WHERE
            HP.state = 'paid' AND
            HC.code IN %(code)s AND
            PP.end > %(start)s AND
            PP.start < %(end)s AND
            HP.contract_id IN %(contracts)s AND
            HPL.payslip_id NOT IN %(payslips)s
        GROUP BY HP.contract_id, HC.code
        """
        data = orm.fetchall(self._cr, query, param)
        for d in data:
            if d[0] not in total_concepts:
                total_concepts[d[0]] = {d[1]: d[2]}
            elif d[1] not in total_concepts[d[0]]:
                total_concepts[d[0]][d[1]] = d[2]
            else:
                total_concepts[d[0]][d[1]] += d[2]

    def to_paid(self):
        holidays_books = []
        leave_category_type = {
            'VAC': 'days_enjoyed',
            'VAC_MONEY': 'days_paid',
            'NO_PAY': 'days_suspension'
        }
        holidays_ids = []
        for record in self:
            if record.state != 'draft':
                continue
            for payslip_line in record.payslip_line_ids:
                if payslip_line.leave_id:
                    leave_id = payslip_line.leave_id
                    holidays_ids.append(leave_id.id)
                    if leave_id.category_type in leave_category_type:
                        holidays_books.append({
                            'contract_id': record.contract_id.id,
                            'leave_id': leave_id.id,
                            'payslip_id': record.id,
                            leave_category_type[leave_id.category_type]: payslip_line.qty
                        })
            record.state = 'paid'
        self.env['hr.leave.line'].search(
            [('payslip_id', 'in', self.ids)]).write({'state': 'paid'})
        self.env['hr.leave'].browse(holidays_ids).to_paid()
        orm.create(self._cr, self.env.uid, 'hr.holiday.book',
                   holidays_books, progress=True)

    def to_draft(self):
        holidays_ids = []
        payslip_ids = [x.id for x in self if x.state == 'paid']
        leave_line_ids = self.env['hr.leave.line'].search(
            [('payslip_id', 'in', payslip_ids)])
        leave_ids = list(dict.fromkeys(
            [x.leave_id.id for x in leave_line_ids]))
        self.env['hr.leave'].browse(
            leave_ids).write({'state': 'validated'})
        leave_line_ids.write({'state': 'validated'})
        self.browse(payslip_ids).write({'state': 'draft'})
        self.env['hr.holiday.book'].search(
            [('payslip_id', 'in', payslip_ids)]).unlink()

    def compute_slip(self, _cr=False):
        data_to_remove = {
            'hr.payslip.line': [],
            'hr.payslip.day': [],
        }
        data_to_create = {
            'hr.payslip.line': [],
            'hr.payslip.day': [],
        }
        sorted_concepts = {}
        categories_novelty = {}
        economic_variables = {
            'SMMLV': {},
            'SUB_TRANS': {},
            'UVT': {},
            'TSDES': {},
            'TRTEFTE': {},
        }
        global_error_log = ''
        politics = self._get_politics()
        total_previous = {}
        total_concepts = {}
        self._get_categories_search(
            total_previous,
            self[0].period_id.start.replace(day=1),
            self[0].period_id.end)
        self._get_concepts_search(
            total_concepts,
            self[0].period_id.start.replace(day=1),
            self[0].period_id.end)
        cr = orm.create_cursor(self._cr)
        len_self = len(self)
        value_eval = int(len_self/10) if int(len_self/10) > 0 else 1
        for i, record in enumerate(self):
            if i % value_eval == 0:
                orm.log_message(f'Calculando {i+1} de {len_self} Nóminas')
            record.error_log = ''
            record.payslip_type_id.get_sorted_concepts(sorted_concepts)
            record.payslip_type_id.get_categories_novelty(categories_novelty)
            payslip_line_novelty = []
            payslip_day_ids = []
            payslip_line_concept = []
            try:
                record.evaluate_constraints()
                record.check_economic_variables(economic_variables)
                data_payslip = record.create_data_payslip(
                    economic_variables, politics, total_previous, total_concepts, cr)
            except ValidationError as ex:
                global_error_log += record.create_error_log(ex.name)
                continue

            data_to_remove['hr.payslip.line'] += record.payslip_line_ids.ids
            data_to_remove['hr.payslip.day'] += record.payslip_day_ids.ids

            # Novedades, Horas Extras, Ausencias
            record.compute_payslip_novelty(
                payslip_line_novelty, payslip_day_ids, data_payslip, categories_novelty)
            data_to_create['hr.payslip.line'] += payslip_line_novelty

            # Dias de Nómina
            data_payslip['worked_days'] = record.compute_worked_days(
                payslip_day_ids, data_payslip)
            data_to_create['hr.payslip.day'] += payslip_day_ids

            # Conceptos de Nómina
            error_log = record.compute_payslip_line_concept(
                payslip_line_concept, data_payslip, sorted_concepts)
            if error_log:
                global_error_log += error_log
            data_to_create['hr.payslip.line'] += payslip_line_concept

        for d2r in data_to_remove:
            orm.delete(self._cr, self.env.uid, d2r,
                       {'id': data_to_remove[d2r]}, cr_aux=_cr)
        for d2c in data_to_create:
            orm.create(self._cr, self.env.uid, d2c,
                       data_to_create[d2c], progress=True, cr_aux=_cr)
        return global_error_log

    def evaluate_constraints(self):
        if self.state != 'draft':
            raise ValidationError('No está en estado borrador')
        if self.contract_id.date_start > self.period_id.end:
            raise ValidationError(
                'Le fecha de inicio del contrato es mayor a la fecha de inicio del periodo a calcular')

    def create_data_payslip(self, economic_variables, politics, total_previous, total_concepts, cr):
        c_obj = self.contract_id
        p_obj = self.period_id
        data_payslip = {
            'contract': c_obj,
            'period': p_obj,
            # Se debe buscar el salario de este periodo
            # Tener cuidado con el diccionario que se construye
            'wage': c_obj.get_wage(p_obj.end, p_obj.start),
            'payslip_id': self.id,
            'economic_variables': economic_variables,
            'politics': politics,
            TPCT: total_previous[c_obj.id] if c_obj.id in total_previous else {},
            TPCP: total_concepts[c_obj.id] if c_obj.id in total_concepts else {},
            NCI: 0,
            'cr': cr,
        }
        return data_payslip

    def compute_payslip_novelty(self, payslip_line_novelty, payslip_day_ids, data_payslip, categories_novelty):
        domain = [('state', '=', 'validated'),
                  ('period_id', '=', self.period_id.id),
                  ('contract_id', '=', self.contract_id.id)]
        categories = categories_novelty.get(self.payslip_type_id.id, {})
        wage = data_payslip['wage'].get('wage', 0) / 30
        key = 'value_total_leave'
        for model in ['hr.novelty.line', 'hr.leave.line', 'hr.overtime']:
            if model not in categories:
                continue
            payslip_novelty_ids = self.env[model].search(domain)
            for payslip_novelty in payslip_novelty_ids:
                if not payslip_novelty.belongs_category(categories[model]):
                    continue
                if model == 'hr.leave.line' and payslip_novelty.leave_id.category_type != 'VAC_MONEY':
                    payslip_day_ids.append(
                        {'payslip_id': self.id, 'day': payslip_novelty.date.day, 'day_type': 'A'})
                    if payslip_novelty.leave_id.category_type in ['SICKNESS', 'AT_EP', 'NO_PAY', 'PAY', 'VAC']:
                        data_payslip[key] = data_payslip.get(key, 0) + wage
                elif model == 'hr.novelty.line':
                    payslip_novelty.check_modality_rtefte(data_payslip)
                # Borrar conceptos de otras nominas
                payslip_novelty.payslip_id = self.id
                new_payslip_line = payslip_novelty.create_payslip_line(self.id)
                create = True
                for payslip_line in payslip_line_novelty:
                    if payslip_line['unique_key'] == new_payslip_line['unique_key']:
                        create = False
                        payslip_line['qty'] += new_payslip_line['qty']
                        payslip_line['total'] += new_payslip_line['total']
                        break
                if create:
                    payslip_line_novelty.append(new_payslip_line)
        for payslip_line in payslip_line_novelty:
            self.update_data_payslip(data_payslip, payslip_line)
            if 'unique_key' in payslip_line:
                payslip_line.pop('unique_key')

    def compute_worked_days(self, payslip_day_ids, data_payslip):
        no_worked_days = [x['day'] for x in payslip_day_ids]
        max_worked_days = 30 if self.period_id.type_period == "MONTHLY" else 15
        wage_day = data_payslip['wage'].get('wage', 0) / 30
        has_last_wage = 'last_wage' in data_payslip['wage']
        wage_last_day = data_payslip['wage'].get('last_wage', 0) / 30
        amount = 0
        date_tmp = self.period_id.start
        while date_tmp <= self.period_id.end:
            if date_tmp < self.contract_id.date_start or (self.contract_id.settlement_date and date_tmp > self.contract_id.settlement_date):
                payslip_day_ids.append(
                    {'payslip_id': self.id, 'day': date_tmp.day, 'day_type': 'X'})
                max_worked_days -= 1 if date_tmp.day != 31 else 0
            elif date_tmp.day not in no_worked_days:
                payslip_day_ids.append(
                    {'payslip_id': self.id, 'day': date_tmp.day, 'day_type': 'W'})
                if date_tmp.day != 31:
                    pay_wage_last = has_last_wage and date_tmp < data_payslip['wage']['date']
                    value = wage_last_day if pay_wage_last else wage_day
                    amount += value
                    if date_tmp.month == 2 and date_tmp.day == monthrange(date_tmp.year, date_tmp.month)[1]:
                        amount += value * 2 if date_tmp.day == 28 else value
            else:
                max_worked_days -= 1 if date_tmp.day != 31 else 0
            date_tmp += timedelta(days=1)
        data_payslip['wage'] = amount
        data_payslip['full_wage'] = wage_day * 30
        return max_worked_days

    def compute_payslip_line_concept(self, payslip_line_concept, data_payslip, sorted_concepts):
        for concept_id in sorted_concepts[self.payslip_type_id.id]:
            # Los aportes se calculan en PILA
            if concept_id.category == 'contributions':
                continue
            if concept_id.code not in CONCEPTS:
                continue
            try:
                payslip_line = eval(
                    'concept_id._' + concept_id.code + '(data_payslip)')
                if type(payslip_line) == dict:
                    self.update_data_payslip(data_payslip, payslip_line)
                    payslip_line_concept.append(payslip_line)
            except ValidationError as ex:
                return self.create_error_log(ex.name)

    def update_data_payslip(self, data_payslip, payslip_line):
        if payslip_line['category'] in data_payslip:
            data_payslip[payslip_line['category']] += payslip_line['total']
        else:
            data_payslip[payslip_line['category']] = payslip_line['total']

    def check_economic_variables(self, economic_variables):
        for ev in economic_variables:
            year = self.period_id.start.year if ev != 'TSDES' else self.period_id.start.year - 1
            if year not in economic_variables[ev]:
                economic_variables[ev][year] = self.env['economic.variable'].get_value(
                    ev, year)

    def create_error_log(self, message):
        self.error_log = f'{self.name}: {message}\n'
        return self.error_log
