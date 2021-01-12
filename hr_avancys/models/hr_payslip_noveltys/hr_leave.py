# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
from odoo.addons.avancys_tools import orm
from odoo.addons.avancys_tools.time import days360
from calendar import monthrange
from .hr_leave_type import CATEGORY_TYPE


class HrLeave(models.Model):
    _name = 'hr.leave'
    _inherit = 'model.basic.payslip.novelty'
    _description = 'Ausencia'
    _order = 'name'

    leave_type_id = fields.Many2one(
        comodel_name='hr.leave.type', string='Categoría de Ausencia', required=True)
    leave_line_ids = fields.One2many(
        comodel_name='hr.leave.line', inverse_name='leave_id', readonly=True, string='Lineas de Ausencia')
    date_end = fields.Date(string='Fecha Final', required=True)
    amount = fields.Float(string='Valor', readonly=True,
                          compute='_compute_amount', store=True)
    category_type = fields.Selection(
        string='Tipo', selection=CATEGORY_TYPE,
        readonly=True, related='leave_type_id.category_type')
    days_vac_money = fields.Integer(string='Cantidad de días')
    number_order_eps = fields.Char(string='Número autorización')
    cause_id = fields.Many2one(
        comodel_name='hr.leave.cause', string='Diagnóstico')
    is_extension = fields.Boolean(string='Es prórroga', default=False)
    extension_id = fields.Many2one(comodel_name='hr.leave', string='Prórroga')

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code(
            'seq.hr.leave') or ''
        return super(HrLeave, self).create(vals)

    @api.depends('leave_line_ids')
    def _compute_amount(self):
        for record in self:
            record.amount = sum([x.amount for x in record.leave_line_ids])

    @api.onchange('contract_id', 'leave_type_id')
    def _onchange_contract_id_leave_type_id(self):
        res = {
            'value': {
                'is_extension': False,
                'extension_id': False,
            },
        }
        return res

    @api.onchange('is_extension')
    def _onchange_is_extension(self):
        if not self.is_extension:
            res = {
                'value': {
                    'extension_id': False,
                },
            }
            return res

    def to_validated(self):
        period = self.env['hr.period']
        for record in self:
            if record.state != 'confirm':
                continue
            if record.category_type == 'VAC_MONEY':
                record.date_end = record.date_start
            else:
                overlap = self.env['hr.leave.line'].search(
                    [('date', '>=', record.date_start), ('date', '<=', record.date_end),
                     ('contract_id', '=', record.contract_id.id)])
                if [x for x in overlap if x.leave_id.category_type != 'VAC_MONEY']:
                    raise ValidationError(
                        'Las ausencias no permiten sobrelapamiento.')
            if not record.date_start:
                raise ValidationError('Se debe definir la fecha de inicio.')
            if not record.date_end:
                raise ValidationError('Se debe definir la fecha de fin.')
            if record.date_end < record.date_start:
                raise ValidationError(
                    'La fecha de fin debe ser mayor o igual a la fecha de inicio.')
            periods = period.get_period(
                record.date_start, record.date_end, record.contract_id.schedule_pay)
            record.leave_line_ids = record._prepare_leave_line(periods)
        return super(HrLeave, self).to_validated()

    def to_draft(self):
        for record in self:
            if record.state != 'validated':
                continue
            record.leave_line_ids.unlink()
        return super(HrLeave, self).to_draft()

    def _prepare_leave_line(self, periods):
        new_leave_line = []
        if not periods:
            raise ValidationError(
                f'No hay períodos en estas fechas {self.date_start} y {self.date_end}')
        economic_variables = {
            'SMMLV': {},
        }
        self.env['economic.variable']._get_economic_variables(
            economic_variables, self.date_start.year)
        economic_variables['wage'] = self.contract_id.get_wage(
            self.date_start)['wage']
        politics = self.leave_type_id.get_politics_leave()
        smmlv_day = economic_variables['SMMLV'][self.date_start.year]/30
        date_tmp = self.date_start
        sequence, date_origin = self.get_sequence_and_date()
        economic_variables['date_origin'] = date_origin
        amount = 0
        type_id = self.leave_type_id
        if not type_id.category_type:
            raise ValidationError('La categoría de la ausencia no tiene tipo')
        amount = eval(f'self._{type_id.category_type}(economic_variables)')
        while date_tmp <= self.date_end:
            if not(date_tmp.day == 31 and type_id.category_type != 'VAC_MONEY' and not type_id.apply_day_31):
                period = [x for x in periods if x.start <= date_tmp <= x.end]
                if not period:
                    raise ValidationError(
                        f'No se encontró un período para el día {date_tmp}')
                elif len(period) > 1:
                    raise ValidationError(
                        f'Se encontraron {len(period)} períodos para este día {date_tmp}')

                if politics.get('hr_avancys.pays_eg_b2_with_wage', False) and sequence <= 2:
                    amount_real = economic_variables['wage'] / 30
                elif politics.get('hr_avancys.pays_atep_b1_with_wage', False) and sequence == 1:
                    amount_real = economic_variables['wage'] / 30
                else:
                    amount_real = amount * \
                        type_id.get_rate_concept_id(sequence)[0] / 100

                if amount_real < smmlv_day and type_id.category_type != 'NO_PAY':
                    amount_real = smmlv_day
                new_leave_line.append((0, 0, {
                    'sequence': sequence,
                    'date': date_tmp,
                    'period_id': period[0].id,
                    'state': 'validated',
                    'amount': amount_real,
                }))
                sequence += 1
                if date_tmp == self.date_end:
                    self.check_deduction_days(
                        new_leave_line, date_tmp, sequence, amount_real)
            date_tmp += timedelta(days=1)
        return new_leave_line

    def to_paid(self):
        for record in self:
            paid = True
            for leave_line in record.leave_line_ids:
                paid &= leave_line.state == 'paid'
            if paid:
                record.state = 'paid'

    def to_cancel(self):
        for record in self:
            if record.state == 'validated':
                record.leave_line_ids.unlink()
        return super(HrLeave, self).to_cancel()

    def _SICKNESS(self, economic_variables):
        return self.get_ibc(economic_variables)

    def _MAT_LIC(self, economic_variables):
        return self.get_average_last_year(economic_variables, ['earnings'])

    def _PAT_LIC(self, economic_variables):
        return self.get_average_last_year(economic_variables, ['earnings'])

    def _AT_EP(self, economic_variables):
        return self.get_ibc(economic_variables)

    def _NO_PAY(self, economic_variables):
        return 0

    def _PAY(self, economic_variables):
        return economic_variables['wage'] / 30

    def _VAC(self, economic_variables):
        return self.get_average_last_year(economic_variables, ['earnings', 'o_salarial_earnings'])

    def _VAC_MONEY(self, economic_variables):
        base = self.get_average_last_year(
            economic_variables, ['earnings', 'o_salarial_earnings', 'comp_earnings'])
        return base * self.days_vac_money

    def get_ibc(self, economic_variables):
        period = self.env['hr.period']
        data = {
            'contract': self.contract_id,
            'economic_variables': economic_variables,
            'period': period.get_period(self.date_start, False, 'MONTHLY'),
        }
        ref_date = economic_variables['date_origin'] - relativedelta(months=1)
        previous_period = period.get_period(ref_date, False, 'MONTHLY')
        self._get_total_concept_categories(data, previous_period)
        self.env['hr.concept']._compute_ibd(data)
        base = data.get('IBD', 0)
        base = base if base else economic_variables['wage']
        return base / 30

    def get_average_last_year(self, economic_variables, categories):
        data = {}
        date_to = self.date_start - relativedelta(months=1)
        date_to = date_to.replace(
            day=monthrange(date_to.year, date_to.month)[1])
        date_from = date_to.replace(day=1) - relativedelta(years=1)
        if self.contract_id.date_start > date_from:
            date_from = self.contract_id.date_start
        period = {'start': date_from, 'end': date_to}
        self._get_total_concept_categories(
            data, period, exclude=('BASICO',))
        average = economic_variables['wage']
        days = days360(date_from, date_to)
        for category in categories:
            average += data.get(category, 0) * (1 if days < 30 else 30/days)
        return average / 30

    def _get_total_concept_categories(self, total_previous, period, exclude=False):
        cr = orm.create_cursor(self._cr)
        self.env['hr.concept']._get_total_concept_categories(
            cr, total_previous, period, self.contract_id.id, exclude=exclude)

    def get_sequence_and_date(self):
        category_type = self.leave_type_id.category_type
        if self.category_type in ['SICKNESS', 'AT_EP']:
            start = self.date_start
            blacklist = [self.id]
            extension_id = self.extension_id
            while extension_id:
                if extension_id.id in blacklist:
                    raise ValidationError(
                        f'Error de prórroga de si misma, validar ancestros de ausencia {self.name}')
                blacklist.append(extension_id.id)
                start = extension_id.date_start
                extension_id = extension_id.extension_id
            return max([x.sequence for x in self.extension_id.leave_line_ids] + [0]) + 1, start
        else:
            return 1, self.date_start

    def check_deduction_days(self, new_leave_line, date_ref, sequence, amount_real):
        type_id = self.leave_type_id
        if not(type_id.category_type == 'NO_PAY' and type_id.discount_rest_day):
            return
        hr_period = self.env['hr.period']
        schedule = self.contract_id.resource_calendar_id
        days = [int(x.dayofweek) for x in schedule.attendance_ids]
        for i in range(7):
            date_ref += timedelta(days=1)
            if date_ref.weekday() not in days:
                period = hr_period.get_period(
                    date_ref, False, self.contract_id.schedule_pay)
                if not period:
                    raise ValidationError(
                        f'No se encontró periodo para esta fecha {date_ref}')
                new_leave_line.append((0, 0, {
                    'sequence': sequence,
                    'date': date_ref,
                    'period_id': period.id,
                    'state': 'validated',
                    'amount': amount_real,
                }))
                sequence += 1
