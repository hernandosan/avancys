# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.addons.avancys_tools import orm
from odoo.addons.avancys_tools.time import days360
from dateutil.relativedelta import relativedelta

############################################################################
# ------------------- SOLO SE SOPORTAN ValidationError --------------------#
############################################################################

CONCEPTS = [
    'BASICO', 'SUB_TRANS', 'IBD',  'DED_PENS', 'DED_EPS', 'FOND_SOL',
    'FOND_SUB', 'PRIMA_LIQ', 'CES_LIQ',
    'BRTF', 'RTEFTE',
    'VAC_LIQ', 'INDEM', 'RTF_INDEM',
    'NETO'
]
TPCT = 'total_previous_categories'
TPCP = 'total_previous_concepts'
NCI = 'non_constitutive_income'
# 'ANT', 'AP_ARL', 'AP_CCF', 'AP_EPS', 'AP_ICBF', 'AP_PENS', 'AP_SENA',
# 'ATEP', 'ATEP_P2',   'CES', 'CESLY', 'CES_LIQ', 'CES_PART',
# 'COSTO', 'ICES', 'ICESLY', 'ICES_LIQ', 'ICES_PART', 'INDEM',
# 'MAT_LIC',  'NETO_CES', 'NETO_LIQ', 'PAT_LIC', 'PRIMA', 'PRIM_LIQ',
# 'PRV_CES', 'PRV_ICES', 'PRV_PRIM', 'PRV_VAC', 'RET_CTG_AFC', 'RET_CTG_DIF_AFC',
# 'RET_CTG_DIF_FVP', 'RET_CTG_FVP',  'RTF_INDEM', 'RTF_PRIMA', 'SUB_CONNE',
# 'TOT_DED', 'TOT_DEV', 'VAC_DISF', 'VAC_LIQ', 'VAC_PAG'


class HrConceptType(models.Model):
    _name = 'hr.concept'
    _inherit = 'model.basic.payslip.novelty.type'
    _description = 'Concepto de Nómina'
    _order = 'name'

    documentation = fields.Char(string='Información')

    def get_seq_concept_category(self):
        for i, concept in enumerate(CONCEPTS):
            if concept == self.code:
                return i
        return len(CONCEPTS)

    def _compute_ibd(self, data_payslip):
        salary = 0
        for category in ['earnings', 'o_salarial_earnings', 'comp_earnings', 'o_rights']:
            salary += data_payslip.get(TPCT, {}).get(category, 0)
            salary += data_payslip.get(category, 0)
        o_earnings = data_payslip.get(TPCT, {}).get('o_earnings', 0)
        o_earnings += data_payslip.get('o_earnings', 0)
        top40 = (salary + o_earnings) * 0.4
        if o_earnings > top40:
            data_payslip['IBD'] = salary + o_earnings - top40
        else:
            data_payslip['IBD'] = salary
        if data_payslip['contract'].contract_type_id.type_class == 'int':
            data_payslip['IBD'] *= 0.7
        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['period'].start.year]
        if data_payslip['IBD'] > 25 * smmlv:
            data_payslip['IBD'] = 25 * smmlv

    def _compute_brtf(self, data_payslip):
        total_income = 0
        for category in ['earnings', 'o_earnings', 'o_salarial_earnings', 'comp_earnings', 'o_rights']:
            total_income += data_payslip.get(TPCT, {}).get(category, 0)
            total_income += data_payslip.get(category, 0)
        total_income -= data_payslip.get('income_EXT', 0)
        if data_payslip['contract'].apply_procedure_2:
            for concept in ['PRIMA', 'PRIMA_LIQ']:
                total_income += data_payslip.get(TPCP, {}).get(concept, 0)
                total_income += data_payslip.get(concept, 0)

        total_nci = data_payslip[NCI]
        for nci in ['DED_PENS', 'DED_EPS', 'FOND_SOL', 'FOND_SUB']:
            total_nci += data_payslip.get(TPCP, {}).get(nci, 0)
        neto_income = total_income - total_nci
        if neto_income == 0:
            data_payslip['BRTF'] = 0
            return

        # Deducciones
        uvt = data_payslip['economic_variables']['UVT'][data_payslip['period'].start.year]
        if data_payslip['contract'].deduction_dependents:
            deduction_base = total_income * 0.1
            deduction_dependents = deduction_base if deduction_base <= 32 * uvt else 32 * uvt
        else:
            deduction_dependents = 0

        if data_payslip['contract'].deduction_by_estate <= 100 * uvt:
            deduction_estate = data_payslip['contract'].deduction_by_estate
        else:
            deduction_estate = 100 * uvt

        if data_payslip['contract'].deduction_by_healthcare <= 16 * uvt:
            deduction_healthcare = data_payslip['contract'].deduction_by_healthcare
        else:
            deduction_healthcare = 16 * uvt

        if data_payslip['contract'].deduction_by_icetex <= 8.333 * uvt:
            deduction_icetex = data_payslip['contract'].deduction_by_icetex
        else:
            deduction_icetex = 8.333 * uvt

        deduction_total = deduction_dependents + deduction_estate + \
            deduction_healthcare + deduction_icetex

        AVP = data_payslip.get('outcome_AVP', 0)
        AFC = data_payslip.get('outcome_AFC', 0)
        voluntary_contributions = AVP + AFC
        if voluntary_contributions > neto_income * 0.3:
            voluntary_contributions = neto_income * 0.3

        top25 = (neto_income - deduction_total -
                 voluntary_contributions) * 0.25
        if top25 > 240 * uvt:
            top25 = 240 * uvt

        top40 = neto_income * 0.4 if neto_income * 0.4 <= 420 * uvt else 420 * uvt
        exempt_rent = deduction_total + voluntary_contributions + top25
        if exempt_rent > top40:
            exempt_rent = top40

        data_payslip['BRTF'] = neto_income - exempt_rent

    def _compute_indem(self, data_payslip):
        settlement_type = data_payslip['contract'].settlement_type
        if not settlement_type:
            raise ValidationError('El contrato no tiene tipo de finalización.')
        elif settlement_type not in ['n_causa', 'unil']:
            return
        term = data_payslip['contract'].term
        settlement_date = data_payslip['contract'].settlement_date
        if not settlement_date:
            raise ValidationError('El contrato no tiene fecha de liquidación.')
        if 'last_year' not in data_payslip:
            self.get_last_year(data_payslip)
        if term in ['fijo', 'obra-labor']:
            date_end = data_payslip['contract'].date_end
            if not date_end:
                raise ValidationError('El contrato no tiene fecha de fin.')
            if settlement_date > date_end:
                raise ValidationError(
                    'La fecha de liquidación debe ser menor o igual a la fecha de fin.')
            days_not_pay = days360(settlement_date, date_end) - 1
            if days_not_pay <= 0:
                return
            value, qty = data_payslip['last_year']['average'], days_not_pay
            if term == 'obra-labor' and qty < 15:
                qty = 15
        else:
            date_start = data_payslip['contract'].date_start
            if not date_start:
                raise ValidationError('El contrato no tiene fecha de inicio.')
            duration = days360(date_start, settlement_date)
            value = data_payslip['last_year']['average']
            smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['period'].start.year]
            qty, days = [30, 20] if value < 10 * smmlv / 30 else [20, 15]
            qty += (duration - 360)*days/360 if duration > 361 else 0
        data_payslip['INDEM_value'] = value
        data_payslip['INDEM_qty'] = qty

    def _compute_social_benefits(self, data_payslip, date_from, date_to):
        days_worked = days360(date_from, date_to)
        data = {
            'contract': data_payslip['contract'].id,
            'start': date_from,
            'end': date_to,
            'type': ('MAT_LIC', 'PAT_LIC')
        }
        hll = self.env['hr.leave.line']
        days_license, amount_license = hll.get_info_from_leave_type(
            data_payslip['cr'], data)
        days = days_worked - days_license

        data_vs = {}
        self.get_variable_salary(
            data_payslip['cr'], data_vs, data, data['contract'])
        data_base = {
            'variable': sum(data_vs.values()),
            'salary': self.get_salary_in_leave(data_payslip['cr'], data)
        }
        ces = ['CESLY', 'ICESLY', 'CES', 'ICES', 'CES_PART',
               'ICES_PART', 'CES_LIQ', 'ICES_LIQ', 'PRV_CES', 'PRV_ICES']
        if data_payslip['politics']['hr_avancys.discount_suspensions'] or self.code in ces:
            data['type'] = ('NO_PAY',)
            days_worked -= hll.get_info_from_leave_type(
                data_payslip['cr'], data)[0]
        else:
            data_base['salary'] += data_payslip.get('value_total_leave', 0)
        concepts = ('BASICO', 'SUB_TRANS', 'SUB_CONNE')
        data_salary = {}
        self._get_total_concepts(
            data_payslip['cr'], data_salary, data, data['contract'], concepts)
        for concept in concepts:
            key = 'salary' if concept == 'BASICO' else 'static'
            data_base[key] = data_base.get(key, 0)
            data_base[key] += data_salary.get(concept, 0)
            data_base[key] += data_payslip.get(concept, 0)

        if not data_payslip['politics']['hr_avancys.average_sub_trans']:
            smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['period'].start.year]
            average_earnings = data_base['salary'] + data_vs.get('earnings', 0)
            average_earnings *= 30 / days if days > 30 else 1
            if average_earnings < 2 * smmlv:
                subsidy = data_payslip['economic_variables']['SUB_TRANS'][data_payslip['period'].start.year]
                data_base['static'] = subsidy * days_worked / 30

        base = sum(data_base.values()) + amount_license
        base *= 1 if days_worked <= 30 else 30 / days_worked
        total = base * days_worked / 360
        return base, days_worked, total

    def _compute_rate_fond_sol(self, smmlv, value):
        return 0.5 if value >= 4 * smmlv else 0

    def _compute_rate_fond_sub(self, smmlv, value):
        if value < 4 * smmlv:
            return 0
        elif 4 * smmlv <= value < 16 * smmlv:
            return 0.5
        elif 16 * smmlv <= value < 17 * smmlv:
            return 0.7
        elif 17 * smmlv <= value < 18 * smmlv:
            return 0.9
        elif 18 * smmlv <= value < 19 * smmlv:
            return 1.1
        elif 19 * smmlv <= value < 20 * smmlv:
            return 1.3
        else:
            return 1.5

    def _get_rate_trtefte(self, data_payslip, value):
        uvt = data_payslip['economic_variables']['UVT'][data_payslip['period'].start.year]
        table = data_payslip['economic_variables']['TRTEFTE'][data_payslip['period'].start.year]
        if uvt == 0:
            raise ValidationError(
                'La UVT definida para el año %s es cero.' % data_payslip['period'].start.year)
        base = value / uvt
        subtract, rate, add, lower_limit, upper_limit = [x for x in range(5)]
        rtefte = 0
        for t in table:
            compute = False
            if t[lower_limit] == None and t[upper_limit] != None and base <= t[upper_limit]:
                compute |= True
            elif None not in t[lower_limit:upper_limit-1] and t[lower_limit] < base <= t[upper_limit]:
                compute |= True
            elif t[lower_limit] != None and t[upper_limit] == None and t[lower_limit] < base:
                compute |= True
            if compute:
                rtefte = (base - t[subtract]) * t[rate] / 100 + t[add]
                rtefte *= uvt * 100 / value
        return rtefte

    def _get_total_concepts(self, cr, total_previous, period, contract, concepts):
        """
        Consulta las lineas de nomina y agrupa por categoria
        @params:
            total_previous: Diccionario donde se guardaran los datos
            period: Objeto tipo hr.period o Dicionario con {inicio,fin}
            contract: ID del contrato
            concepts: Tupla de conceptos a consultar
        @return:
            None
        """
        param = {
            'concepts': concepts,
            'contract': contract,
            'start': period.start if type(period) != dict else period['start'],
            'end': period.end if type(period) != dict else period['end'],
        }
        query = f"""
        SELECT HC.code, sum(HPL.total)
        FROM hr_payslip_line as HPL
        INNER JOIN hr_concept as HC
            ON HC.id = HPL.concept_id
        INNER JOIN hr_payslip as HP
            ON HP.id = HPL.payslip_id
        INNER JOIN hr_period as PP
            ON PP.id = HP.period_id
        WHERE
            HP.state = 'paid' AND
            PP.end >= %(start)s AND
            PP.start <= %(end)s AND
            HP.contract_id = %(contract)s AND
            HC.code in %(concepts)s
        GROUP BY HC.code
        """
        data = orm._fetchall(cr, query, param)
        for d in data:
            if d[0] not in total_previous:
                total_previous[d[0]] = d[1]
            else:
                total_previous[d[0]] += d[1]

    def _get_total_concept_categories(self, cr, total_previous, period, contract, exclude=False, categories=False):
        """
        Consulta las lineas de nomina y agrupa por categoria
        @params:
            total_previous: Diccionario donde se guardaran los datos
            period: Objeto tipo hr.period o Dicionario con {'start','end'}
            contract: ID del contrato
            exclude: Tupla con codigo de conceptos a excluir
            categories: Tupla de categorias a consultar
        @return:
            None
        """
        if not categories:
            categories = ('earnings', 'o_salarial_earnings',
                          'comp_earnings', 'o_rights', 'o_earnings')
        param = {
            'categories': categories,
            'contract': contract,
            'start': period.start if type(period) != dict else period['start'],
            'end': period.end if type(period) != dict else period['end'],
        }
        subquery = ['', '']
        if exclude:
            subquery[0] = "LEFT JOIN hr_concept as HC ON HC.id = HPL.concept_id"
            subquery[1] = "AND (HC.code IS NULL or HC.code not in %(exclude)s)"
            param['exclude'] = exclude
        query = f"""
        SELECT HPL.category, sum(HPL.total)
        FROM hr_payslip_line as HPL
        INNER JOIN hr_payslip as HP
            ON HP.id = HPL.payslip_id
        INNER JOIN hr_period as PP
            ON PP.id = HP.period_id
        {subquery[0]}
        WHERE
            HP.state = 'paid' AND
            HPL.category IN %(categories)s AND
            PP.end >= %(start)s AND
            PP.start <= %(end)s AND
            HP.contract_id = %(contract)s
            {subquery[1]}
        GROUP BY HPL.category
        """
        data = orm._fetchall(cr, query, param)
        for d in data:
            if d[0] not in total_previous:
                total_previous[d[0]] = d[1]
            else:
                total_previous[d[0]] += d[1]

    def get_variable_salary(self, cr, data, period, contract):
        categories = ('earnings', 'comp_earnings', 'o_salarial_earnings')
        self._get_total_concept_categories(cr, data, period, contract,
                                           exclude=('BASICO',), categories=categories)

    def get_salary_in_leave(self, cr, data):
        """
        Construye el salario que se le debio pagar al empleado cuando estaba
        en incapacidad o vacaciones
        @params:
            cr: Cursor
            data: Dicionario con {'contract','start', 'end'}
        @return:
            int
        """
        query = """
        SELECT COALESCE(SUM(TMP.value_day), 0)  FROM(
            SELECT DISTINCT ON(HLL.date) HLL.date, WUH.wage/30 AS "value_day"
            FROM hr_leave_line AS  HLL
            INNER JOIN hr_leave AS HL ON HL.id=HLL.leave_id
            INNER JOIN hr_leave_type AS HLT ON HLT.id=HL.leave_type_id
            INNER JOIN wage_update_history AS WUH ON WUH.contract_id=HL.contract_id
            WHERE
                HL.contract_id = %(contract)s AND HLL.state = 'paid' AND
                HLL.date BETWEEN %(start)s AND %(end)s AND
                HLT.category_type IN ('SICKNESS', 'AT_EP', 'VAC', 'NO_PAY') AND
                HLL.date - WUH.date >= 0
                ORDER BY HLL.date, HLL.date - WUH.date) AS TMP"""
        return orm._fetchall(cr, query, data)[0][0]

    def get_last_year(self, data_payslip):
        if not data_payslip['contract'].settlement_date:
            raise ValidationError('El contrato no tiene fecha de liquidación.')
        date_to = data_payslip['contract'].settlement_date
        date_from = date_to - relativedelta(years=1)
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start
        days = days360(date_from, date_to)
        data_payslip['last_year'] = {
            'start': date_from, 'end': date_to, 'days': days}
        wd = days - self.get_leave_no_pay(
            data_payslip['cr'], data_payslip['contract'].id, data_payslip['last_year'])
        data_payslip['last_year']['worked_days'] = wd
        data = {}
        self.get_variable_salary(
            data_payslip['cr'], data, data_payslip['last_year'], data_payslip['contract'].id)
        average = data_payslip['full_wage']
        for category in data:
            average += data[category] * (1 if wd < 30 else 30/wd)
        data_payslip['last_year']['average'] = average / 30

    def get_holiday_book(self, data_payslip):
        if not data_payslip['contract'].settlement_date:
            raise ValidationError('El contrato no tiene fecha de liquidación.')
        data_payslip['holiday_book'] = data_payslip['contract'].get_holiday_book(
            data_payslip['contract'].settlement_date)

    def get_leave_no_pay(self, cr, contract, period):
        param = {
            'contract': contract,
            'start': period.start if type(period) != dict else period['start'],
            'end': period.end if type(period) != dict else period['end'],
        }
        query = """
        SELECT count(*)
        FROM hr_leave_line as HLL
        INNER JOIN hr_leave as HL
            ON HL.id = HLL.leave_id
        INNER JOIN hr_leave_type as HLT
            ON HLT.id = HL.leave_type_id
        WHERE 
            HL.contract_id = %(contract)s AND
            HLL.date BETWEEN %(start)s AND %(end)s AND
            HLT.category_type = 'NO_PAY'
        """
        res = orm._fetchall(cr, query, param)
        return sum([x[0] for x in res if x[0]])

    ############################################################################
    # ------------------- CALCULO DE CONCEPTOS INDIVIDUALES -------------------#
    ############################################################################

    def _BASICO(self, data_payslip):
        type_class = data_payslip['contract'].contract_type_id.type_class
        if type_class == 'int':
            name, value, rate = 'SUELDO BASICO INTEGRAL', data_payslip['wage'], 1
        elif type_class == 'apr':
            salary_day = data_payslip['wage']
            if data_payslip['contract'].fiscal_type_id.code == '12':
                name, value, rate = 'CUOTA DE SOSTENIMIENTO LECTIVO', salary_day, 0.5
            elif data_payslip['contract'].fiscal_type_id.code == '19':
                name, value, rate = 'CUOTA DE SOSTENIMIENTO PRODUCTIVO', salary_day, 1
                if data_payslip['period'].start < data_payslip['contract'].apprentice_to_worker_date < data_payslip['period'].end:
                    days_lec = data_payslip['contract'].apprentice_to_worker_date.day - \
                        data_payslip['period'].start.day
                    days_prod = data_payslip['worked_days'] - days_lec
                    value = (value*days_lec/2 + value*days_prod) / \
                        data_payslip['worked_days']
            else:
                raise ValidationError(
                    'Defina <Tipo de Cotizante> en el contrato y asegurese de que tenga código. Códigos validos 12 y 19')
        elif type_class == 'reg':
            name, value, rate = self.name, data_payslip['wage'], 1
        else:
            raise ValidationError(
                'No ha definido el tipo de contrato (Regular, Aprendiz o Integral).')
        data_payslip['BASICO'] = value * rate
        return {
            'name': name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': value,
            'qty': data_payslip['worked_days'],
            'rate': rate * 100,
            'total': value * rate,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _SUB_TRANS(self, data_payslip):
        sub_trans = data_payslip['economic_variables']['SUB_TRANS'][data_payslip['period'].start.year] / 30
        portion = 1 if data_payslip['period'].type_period == 'MONTHLY' else 2
        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['period'].start.year]
        value_eval = 2 * smmlv / portion
        if data_payslip.get('earnings', 0) < value_eval or data_payslip['wage'] < value_eval:
            pay = True
            if data_payslip['contract'].fiscal_type_id.code == '19':
                pay &= data_payslip['politics']['hr_avancys.pays_sub_trans_train_prod']
            if not pay:
                return
            if data_payslip['contract'].remote_work_allowance:
                sub_conne = self.env.ref('hr_avancys.hc_sub_conne')
                name = sub_conne.name
                concept_id = sub_conne.id
            else:
                name = self.name
                concept_id = self.id
            total = sub_trans * data_payslip['worked_days']
            data_payslip[self.code] = total
            return {
                'name': name,
                'payslip_id': data_payslip['payslip_id'],
                'category': self.category,
                'value': sub_trans,
                'qty': data_payslip['worked_days'],
                'rate': 100,
                'total': total,
                'origin': 'local',
                'concept_id': concept_id,
                'leave_id': None,
                'novelty_id': None,
                'overtime_id': None,
            }

    def _IBD(self, data_payslip):
        if 'IBD' not in data_payslip:
            self._compute_ibd(data_payslip)
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': data_payslip['IBD'],
            'qty': 1,
            'rate': 100,
            'total': data_payslip['IBD'],
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _DED_PENS(self, data_payslip):
        if 'IBD' not in data_payslip:
            self._compute_ibd(data_payslip)
        rate = data_payslip['politics']['hr_avancys.pen_rate_employee']
        total = data_payslip['IBD'] * rate / 100
        data_payslip[NCI] += total
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': data_payslip['IBD'],
            'qty': 1,
            'rate': rate,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _DED_EPS(self, data_payslip):
        if 'IBD' not in data_payslip:
            self._compute_ibd(data_payslip)
        rate = data_payslip['politics']['hr_avancys.eps_rate_employee']
        total = data_payslip['IBD'] * rate / 100
        data_payslip[NCI] += total
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': data_payslip['IBD'],
            'qty': 1,
            'rate': rate,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _FOND_SOL(self, data_payslip):
        if 'IBD' not in data_payslip:
            self._compute_ibd(data_payslip)
        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['period'].start.year]
        rate = self._compute_rate_fond_sol(smmlv, data_payslip['IBD'])
        if data_payslip['contract'].fiscal_subtype_id.code in ['00', False] and rate:
            previous = data_payslip.get(TPCP, {}).get('FOND_SOL', 0)
            total = data_payslip['IBD'] * rate / 100 - previous
            data_payslip[NCI] += total
            return {
                'name': self.name,
                'payslip_id': data_payslip['payslip_id'],
                'category': self.category,
                'value': data_payslip['IBD'],
                'qty': 1,
                'rate': rate,
                'total': total,
                'origin': 'local',
                'concept_id': self.id,
                'leave_id': None,
                'novelty_id': None,
                'overtime_id': None,
            }

    def _FOND_SUB(self, data_payslip):
        if 'IBD' not in data_payslip:
            self._compute_ibd(data_payslip)
        smmlv = data_payslip['economic_variables']['SMMLV'][data_payslip['period'].start.year]
        rate = self._compute_rate_fond_sub(smmlv, data_payslip['IBD'])
        if data_payslip['contract'].fiscal_subtype_id.code in ['00', False] and rate:
            previous = data_payslip.get(TPCP, {}).get('FOND_SUB', 0)
            total = data_payslip['IBD'] * rate / 100 - previous
            data_payslip[NCI] += total
            return {
                'name': self.name,
                'payslip_id': data_payslip['payslip_id'],
                'category': self.category,
                'value': data_payslip['IBD'],
                'qty': 1,
                'rate': rate,
                'total': total,
                'origin': 'local',
                'concept_id': self.id,
                'leave_id': None,
                'novelty_id': None,
                'overtime_id': None,
            }

    def _BRTF(self, data_payslip):
        if 'BRTF' not in data_payslip:
            self._compute_brtf(data_payslip)
        if data_payslip['BRTF'] == 0:
            return
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': data_payslip['BRTF'],
            'qty': 1,
            'rate': 100,
            'total': data_payslip['BRTF'],
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _RTEFTE(self, data_payslip):
        if 'BRTF' not in data_payslip:
            self._compute_brtf(data_payslip)
        if data_payslip['BRTF'] == 0:
            return
        previous = data_payslip.get(TPCP, {}).get('RTEFTE', 0)
        if data_payslip['contract'].apply_procedure_2:
            rate = data_payslip['contract'].withholding_percent
        else:
            rate = self._get_rate_trtefte(data_payslip, data_payslip['BRTF'])
        if rate == 0 and previous == 0:
            return
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': data_payslip['BRTF'],
            'qty': 1,
            'rate': rate,
            'total': data_payslip['BRTF'] * rate / 100 - previous,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _VAC_LIQ(self, data_payslip):
        if 'last_year' not in data_payslip:
            self.get_last_year(data_payslip)
        average = data_payslip['last_year']['average']
        if 'holiday_book' not in data_payslip:
            self.get_holiday_book(data_payslip)
        days_left = data_payslip['holiday_book']['days_left']
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': average,
            'qty': days_left,
            'rate': 100,
            'total': average * days_left,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _INDEM(self, data_payslip):
        if 'INDEM_value' not in data_payslip or 'INDEM_qty' not in data_payslip:
            self._compute_indem(data_payslip)
        value = data_payslip.get('INDEM_value', 0)
        qty = data_payslip.get('INDEM_qty', 0)
        if value == 0 or qty == 0:
            return
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': value,
            'qty': qty,
            'rate': 100,
            'total': value * qty,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _RTF_INDEM(self, data_payslip):
        if 'INDEM_value' not in data_payslip or 'INDEM_qty' not in data_payslip:
            self._compute_indem(data_payslip)
        value = data_payslip.get('INDEM_value', 0)
        qty = data_payslip.get('INDEM_qty', 0)
        uvt = data_payslip['economic_variables']['UVT'][data_payslip['period'].start.year]
        if value * 30 <= 204 * uvt:
            return
        value *= qty * 0.75
        rate = 20
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': value,
            'qty': 1,
            'rate': rate,
            'total': value * rate / 100,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _PRIMA_LIQ(self, data_payslip):
        if not data_payslip['contract'].settlement_date:
            raise ValidationError('El contrato no tiene fecha de liquidación.')
        date_to = data_payslip['contract'].settlement_date
        from_month = 1 if data_payslip['period'].start.month <= 6 else 7
        date_from = data_payslip['period'].start.replace(
            month=from_month, day=1)
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start
        base, qty, total = self._compute_social_benefits(
            data_payslip, date_from, date_to)
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _CES_LIQ(self, data_payslip):
        if not data_payslip['contract'].settlement_date:
            raise ValidationError('El contrato no tiene fecha de liquidación.')
        date_to = data_payslip['contract'].settlement_date
        date_from = data_payslip['period'].start.replace(month=1, day=1)
        if date_from < data_payslip['contract'].date_start:
            date_from = data_payslip['contract'].date_start
        base, qty, total = self._compute_social_benefits(
            data_payslip, date_from, date_to)
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': base,
            'qty': qty,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }

    def _NETO(self, data_payslip):
        total_earnings = ['earnings', 'o_salarial_earnings',
                          'comp_earnings', 'o_rights', 'o_earnings', 'non_taxed_earnings']
        total_deductions = ['deductions']
        total = 0
        for te in total_earnings:
            total += data_payslip.get(te, 0)
        for td in total_deductions:
            total -= data_payslip.get(td, 0)
        return {
            'name': self.name,
            'payslip_id': data_payslip['payslip_id'],
            'category': self.category,
            'value': total,
            'qty': 1,
            'rate': 100,
            'total': total,
            'origin': 'local',
            'concept_id': self.id,
            'leave_id': None,
            'novelty_id': None,
            'overtime_id': None,
        }
