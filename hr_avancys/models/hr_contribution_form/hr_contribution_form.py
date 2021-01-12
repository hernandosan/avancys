# -*- coding: utf-8 -*-
# resolucion 2388 de 2016
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.addons.avancys_tools import orm
from dateutil.relativedelta import relativedelta
from datetime import datetime
from calendar import monthrange
import base64
import unicodedata

STATE = [
    ('draft', 'Borrador'),
    ('paid', 'Pagada')
]

CONTRIBUTION_LINE = {
    'tde': False, 'tae': False, 'tdp': False, 'tap': False, 'vct': False,
    'afp_to_code': None, 'eps_to_code': None, 'vct_start': None, 'vct_end': None,
    'ups': 0, 'esap_rate': 0, 'esap_cot': 0, 'men_rate': 0, 'men_cot': 0,
    'ap_vol_company': 0, 'fixes': ' ', 'ret_cont_vol': 0, 'aus_auth': None,
    'mat_auth': None, 'gd_amount': 0, 'mat_amount': 0,
}


class HrContributionForm(models.Model):
    _name = 'hr.contribution.form'
    _description = 'Planilla de aportes'
    _order = 'name'

    name = fields.Char(string='Nombre', readonly=True)
    state = fields.Selection(string='Estado', selection=STATE, default='draft')
    period_id = fields.Many2one(
        comodel_name='hr.period', string='Periodo',
        domain=[('active', '=', True), ('type_period', '=', 'MONTHLY')], required=True)
    contract_group_id = fields.Many2one(
        comodel_name='hr.contract.group', string='Grupo de Contrato')
    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company)
    error_log = fields.Text(string='Errores', readonly=True)
    file_pila = fields.Binary(string='Archivo plano', readonly=True)
    file_name = fields.Char(string='Nombre', default='PILA.txt', readonly=True)
    branch_code = fields.Char(string='Código de sucursal')

    contracts_ids = fields.Many2many(
        comodel_name='hr.contract', string='Contratos',
        relation='hr_contribution_form_hr_contract_rel',
        copy=False)
    contribution_line_ids = fields.One2many(
        comodel_name='hr.contribution.form.line', inverse_name='contribution_id',
        string='Detalle de planilla de aportes', copy=False, readonly=True)

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code(
            'seq.hr.contribution.form') or ''
        vals['file_name'] = vals['name'] + '.txt'
        return super(HrContributionForm, self).create(vals)

    def unlink(self):
        contribution_remove = [x.id for x in self if x.state == 'draft']
        orm.delete(self._cr, self.env.uid,
                   'hr_contribution_form_hr_contract_rel', {'hr_contribution_form_id': contribution_remove})
        orm.delete(self._cr, self.env.uid,
                   'hr.contribution.form.line', {'contribution_id': contribution_remove})
        orm.delete(self._cr, self.env.uid,
                   'hr.contribution.form', {'id': contribution_remove})

    def load_contracts_ids(self):
        add_contract = []
        for record in self:
            param = {'period_id': record.period_id.id}
            if record.contract_group_id:
                filter_contract_group_id = "AND contract_group_id = %(contract_group_id)s"
                param['contract_group_id'] = record.contract_group_id.id
            else:
                filter_contract_group_id = ''
            contracts_ids_sel = """
            SELECT HC.id FROM hr_contract as HC
            LEFT JOIN (
                SELECT HCFHC.hr_contract_id AS id
                FROM hr_contribution_form_hr_contract_rel as HCFHC
                INNER JOIN hr_contribution_form HCF
                    ON HCF.id = HCFHC.hr_contribution_form_id
                WHERE
                    HCF.period_id = %(period_id)s
            ) as HCC ON HCC.id = HC.id
            WHERE
                HCC.id IS NULL AND HC.state = 'open'
                {fcg}
            """.format(fcg=filter_contract_group_id)
            contracts_ids = orm.fetchall(self._cr, contracts_ids_sel, param)
            for contract_id in contracts_ids:
                add_contract.append({
                    'hr_contribution_form_id': record.id,
                    'hr_contract_id': contract_id[0],
                })
        orm.create(self._cr, self.env.uid,
                   'hr_contribution_form_hr_contract_rel', add_contract, progress=True)

    def compute_pila(self):
        contribution_line_delete = []
        contribution_line_create = []
        economic_variables = {'SMMLV': {}}
        model = 'ir.config_parameter'
        politics = {
            'hr_avancys.eps_rate_employee': float,
            'hr_avancys.eps_rate_employer': float,
            'hr_avancys.pen_rate_employee': float,
            'hr_avancys.pen_rate_employer': float,
            'hr_avancys.pay_ccf_mat_pat': bool,
        }
        for param in politics:
            politics[param] = (politics[param])(
                self.env[model].sudo().get_param(param))
        cr = orm.create_cursor(self._cr)
        for record in self:
            if record.state != 'draft':
                continue
            self.env['economic.variable']._get_economic_variables(
                economic_variables, record.period_id.start.year)
            record.error_log = ''
            contribution_line_delete += record.contribution_line_ids.ids
            for contract in record.contracts_ids:
                lines_pila = []
                data = {}
                data.update(politics)
                record.get_data(
                    data, cr, economic_variables, contract, record.period_id, lines_pila)
                global_ibc = record.set_limits_ibc(
                    sum([lp[2] for lp in lines_pila]), data['smmlv'])
                wage = contract.get_wage(record.period_id.end)['wage']
                template_line = {
                    'contribution_id': record.id,
                    'contract_id': contract.id,
                    'global_ibc': global_ibc,
                    'exonerated': global_ibc < 10 * data['smmlv'] and not data['int'] and not data['apr'],
                    'ing': 'X' if data['period'].between(data['date_start']) else ' ',
                    'afp_code': contract.afp_pension_id.afp_code if data['retired'] else None,
                    'eps_code': contract.eps_id.eps_code or None,
                    'ccf_code': contract.ccf_id.ccf_code or None if not data['apr'] else None,
                    'arl_code': contract.arl_id.arl_code or None if not data['apr_lec'] else None,
                    'wage': wage if wage >= data['smmlv'] else data['smmlv'],
                    'work_center': contract.workcenter or None,
                    'arl_risk': contract.risk_id.risk_percentage or 0,

                }
                template_line.update(CONTRIBUTION_LINE)
                for lp in lines_pila:
                    new_line = template_line.copy()
                    record.get_indicators(lp, new_line, data)
                    record.get_quotation(lp, new_line, data)
                    record.get_contribution_afp_eps(lp, new_line, data)
                    record.get_contribution_arl_para(lp, new_line, data)
                    record.get_dates(lp, new_line, data)
                    contribution_line_create.append(new_line)
        orm.delete(
            self._cr, self.env.uid, 'hr.contribution.form.line', {'id': contribution_line_delete})
        orm.create(
            self._cr, self.env.uid, 'hr.contribution.form.line', contribution_line_create, progress=True)

    def get_data(self, data, cr, economic_variables, contract, period, lines_pila):
        """
        Construye un diccionario con la informacion necesaria
        @params:
            data: Diccionario donde se almacena la informacion
            cr: Cursor de base de datos
            economic_variables: Diccionario con las variables economiacas
            contract: Objeto hr.contract
            period: Objeto hr.period
            lines_pila: Lista vacia donde se almacenan los detalles de pila por contrato
        @return:
            None
        """
        is_liq = self.period_id.between(contract.settlement_date)
        data.update({
            'cr': cr,
            'is_liq': is_liq,
            'smmlv': economic_variables['SMMLV'][self.period_id.start.year],
            'vac_money': self.get_lines_pila(lines_pila, contract, cr, is_liq),
            'f_type': contract.fiscal_type_id.code,
            'f_subtype': contract.fiscal_subtype_id.code,
            'class': contract.contract_type_id.type_class,
            'apr': contract.fiscal_type_id.code in ['19', '12'],
            'apr_lec': contract.fiscal_type_id.code == '12',
            'int': contract.contract_type_id.type_class == 'int',
            'date_start': contract.date_start,
            'settlement_date': contract.settlement_date,
            'period': self.period_id,
            'apply_ret': contract.state == 'close',
        })
        data.update(
            {'retired': data['apr'] or data['f_subtype'] not in ['00', False]})
        param = {'contract': contract.id,
                 'start': period.start, 'end': period.end}
        query = """
        SELECT COUNT(HNL.amount) FROM hr_novelty_line AS HNL
        INNER JOIN hr_period AS HPP ON HPP.id = HNL.period_id
        INNER JOIN hr_novelty AS HN ON HN.id = HNL.novelty_id
        INNER JOIN hr_novelty_type AS HNT ON HNT.id = HN.novelty_type_id
        WHERE HNT.modality = 'AVP' AND HN.contract_id = %(contract)s
        AND HPP.start BETWEEN %(start)s AND %(end)s AND HNL.state = 'paid'"""
        avp = orm._fetchall(data['cr'], query, param)
        if avp and avp[0] and avp[0][0] and not data['retired']:
            data.update({'avp': True, 'ap_vol_contributor': avp[0][0]})
        else:
            data.update({'avp': False, 'ap_vol_contributor': 0})

    def get_lines_pila(self, lines_pila, contract, cr, is_liq):
        """
        Construye las lineas de la planilla
        @params:
            lines_pila: Lista vacia donde se guardan las lineas de la planilla
            contract: hr_contract
            cr: cursor de base de datos
            is_liq: bool define si el contrato tiene fecha de liquidacion en el periodo
        @return:
            int: valor correspondiente a la suma de vacaciones en dinero y liquidadas
        """
        param = {'start': self.period_id.start,
                 'end': self.period_id.end, 'contract': contract.id}
        hr_concept = self.env['hr.concept']
        query = """
        SELECT HL.id, HLT.category_type, SUM(HLL.amount),
            COUNT(*) FILTER(WHERE EXTRACT(day from HLL.date) != 31),
            HL.date_start, HL.date_end
        FROM hr_leave_line AS HLL
        INNER JOIN hr_leave AS HL
            ON HLL.leave_id = HL.id
        INNER JOIN hr_leave_type AS HLT
            ON HL.leave_type_id = HLT.id
        WHERE HL.contract_id = %(contract)s
        AND HLL.date BETWEEN %(start)s AND %(end)s
        GROUP BY HL.id, HLT.category_type"""
        base_lines = orm._fetchall(cr, query, param)
        ibc_previous = {}
        vac_money = 0
        categories = ('earnings', 'o_salarial_earnings', 'comp_earnings')
        # Construir lineas de pila
        # (leave_id, 'type', amount, days, start, end, previuos_ibc)
        for i, bl in enumerate(base_lines):
            if bl[1] == 'VAC_MONEY':
                vac_money += bl[2]
            elif bl[1] in ['VAC', 'NO_PAY', 'PAY']:
                key = f'{bl[4].year}-{bl[4].month}'
                if key not in ibc_previous:
                    tmp = {}
                    start = bl[4].replace(day=1) - relativedelta(months=1)
                    end = start.replace(day=monthrange(
                        start.year, start.month)[1])
                    period = {'start': start, 'end': end}
                    hr_concept._get_total_concept_categories(
                        cr, tmp, period, contract.id, categories=categories)
                    ibc_previous[key] = sum(tmp.values())
                lines_pila.append(
                    (bl[0], bl[1], ibc_previous[key], bl[3], bl[4], bl[5], bl[2]))
            else:
                lines_pila.append(bl + (bl[2],))
        vac_liq = {}
        hr_concept._get_total_concepts(
            cr, vac_liq, self.period_id, contract.id, ('VAC_LIQ',))
        vac_money += sum(vac_liq.values())
        max_days = contract.settlement_date.day if is_liq else 30
        if max_days > 30:
            max_days = 30
        work_days = max_days - sum([x[3]for x in lines_pila])
        if work_days > 0:
            tmp = {}
            hr_concept._get_total_concept_categories(
                cr, tmp, self.period_id, contract.id, categories=categories)
            amount = sum(tmp.values())
            if amount > 0:
                lines_pila.insert(
                    0, (None, 'MAIN', amount, work_days, None, None, amount))
        return vac_money

    def set_limits_ibc(self, ibc, smmlv):
        if ibc > 25 * smmlv:
            return 25 * smmlv
        elif ibc < smmlv:
            return smmlv
        else:
            return ibc

    def get_indicators(self, lp, new_line, data):
        """
        Agrega a new_line los valores de los indicadores
        @params:
            lp: Tupla de 7 elementos (leave_id, 'type', amount, days, start, end, previuos_ibc)
            new_line: Diccionario con campos de hr.contribution.form.line
            data: Diccionario con informacion relevante
        @return:
            None
        """
        new_line['leave_id'] = lp[0]
        new_line['main'] = 'MAIN' == lp[1]
        new_line['ret'] = 'X' if data['apply_ret'] and data['is_liq'] else ' '
        data['apply_ret'] = False
        new_line['vac_lr'] = 'X' if lp[1] == 'VAC' else 'L' if lp[1] == 'PAY' else ' '
        new_line['sln'] = lp[1] == 'NO_PAY'
        new_line['ige'] = lp[1] == 'SICKNESS'
        new_line['lma'] = lp[1] in ('MAT_LIC', 'PAT_LIC')
        new_line['irl'] = 0 if lp[1] != 'AT_EP' else lp[3]
        new_line['k_start'] = data['date_start'] if new_line['ing'] == 'X' else None
        new_line['k_end'] = data['settlement_date'] if new_line['ret'] == 'X' else None
        if not new_line['ing'] == 'X':
            param = {'contract': new_line['contract_id'],
                     'start': data['period'].start, 'end': data['period'].end}
            query = """
            SELECT date FROM wage_update_history
            where contract_id = %(contract)s AND
            date BETWEEN %(start)s AND %(end)s
            ORDER by date DESC LIMIT 1"""
            vsp = orm._fetchall(data['cr'], query, param)
            new_line['vsp'] = True if vsp else False
            new_line['vsp_start'] = vsp[0][0] if vsp else None
        else:
            new_line['vsp'] = False
            new_line['vsp_start'] = None
        new_line['vst'] = False
        if new_line['main'] and not data['apr']:
            vst = {}
            self.env['hr.concept']._get_total_concept_categories(
                data['cr'], vst, data['period'], new_line['contract_id'],
                exclude=('BASICO',), categories=('earnings', 'comp_earnings', 'o_salarial_earnings'))
            if sum(vst.values()):
                new_line['vst'] = True

        new_line['avp'] = data.get('avp', False)
        new_line['ap_vol_contributor'] = data.get('ap_vol_contributor', 0)
        if new_line['avp']:
            del data['avp'], data['ap_vol_contributor']

    def get_quotation(self, lp, new_line, data):
        """
        Agrega a new_line los valores de los ibcs
        @params:
            lp: Tupla de 7 elementos (leave_id, 'type', amount, days, start, end, previuos_ibc)
            new_line: Diccionario con campos de hr.contribution.form.line
            data: Diccionario con informacion relevante
        @return:
            None
        """
        new_line['pens_days'] = lp[3] if not data['retired'] else 0
        new_line['eps_days'] = lp[3]
        sena_lec_dep = data['f_type'] == '12' and data['f_subtype'] == '00'
        new_line['arl_days'] = lp[3] if not sena_lec_dep else 0
        new_line['ccf_days'] = lp[3] if not data['apr'] else 0
        new_line['w_hours'] = lp[3] * 8
        wage_type = data.get('wage_type', False)
        if wage_type:
            new_line['wage_type'] = wage_type
        else:
            if data['int']:
                new_line['wage_type'] = 'X'
            elif new_line['vst']:
                new_line['wage_type'] = 'V'
            elif data['apr']:
                new_line['wage_type'] = ' '
            else:
                new_line['wage_type'] = 'F'
            data['wage_type'] = new_line['wage_type']
        new_line['eps_ibc'] = self.set_limits_ibc(
            lp[2], data['smmlv'] / 30 * lp[3])
        if (data['apr'] or (data['f_type'] == '01' and data['f_subtype'] in ['01', '03', '06', '04'])) and lp[1] != 'MAIN':
            new_line['pens_ibc'] = 0
        else:
            new_line['pens_ibc'] = new_line['eps_ibc']
        new_line['arl_ibc'] = 0 if data['f_type'] == '12' else new_line['eps_ibc']
        new_line['ccf_ibc'] = 0 if data['apr'] else (
            lp[6] + data.get('vac_money', 0))
        new_line['other_ibc'] = new_line['ccf_ibc'] if not new_line['exonerated'] else 0
        data.pop('vac_money') if 'vac_money' in data else None

    def get_contribution_afp_eps(self, lp, new_line, data):
        """
        Agrega a new_line los valores de los aportes afp y eps
        @params:
            lp: Tupla de 7 elementos (leave_id, 'type', amount, days, start, end, previuos_ibc)
            new_line: Diccionario con campos de hr.contribution.form.line
            data: Diccionario con informacion relevante
        @return:
            None
        """
        if data['retired'] or data['apr']:
            new_line['pens_rate'] = 0
            new_line['fsol'] = 0
            new_line['fsub'] = 0
        elif new_line['sln']:
            new_line['pens_rate'] = data['hr_avancys.pen_rate_employer']/100
            new_line['fsol'] = 0
            new_line['fsub'] = 0
        else:
            hr_concept = self.env['hr.concept']
            new_line['pens_rate'] = (data['hr_avancys.pen_rate_employer'] +
                                     data['hr_avancys.pen_rate_employee'])/100
            new_line['fsol'] = hr_concept._compute_rate_fond_sol(
                data['smmlv'], new_line['global_ibc']) * new_line['pens_ibc'] / 100
            new_line['fsub'] = hr_concept._compute_rate_fond_sub(
                data['smmlv'], new_line['global_ibc']) * new_line['pens_ibc'] / 100

        new_line['pens_cot'] = new_line['pens_rate'] * new_line['pens_ibc']
        new_line['pens_total'] = new_line['pens_cot'] + \
            new_line['ap_vol_contributor']

        if new_line['global_ibc'] >= 10 * data['smmlv'] or data['int'] or data['apr']:
            new_line['eps_rate'] = (data['hr_avancys.eps_rate_employer'] +
                                    data['hr_avancys.eps_rate_employee'])/100
        elif new_line['sln']:
            new_line['eps_rate'] = 0
        else:
            new_line['eps_rate'] = data['hr_avancys.eps_rate_employee'] / 100
        new_line['eps_cot'] = new_line['eps_rate'] * new_line['eps_ibc']

    def get_contribution_arl_para(self, lp, new_line, data):
        """
        Agrega a new_line los valores de los aportes arl y parafiscales
        @params:
            lp: Tupla de 7 elementos (leave_id, 'type', amount, days, start, end, previuos_ibc)
            new_line: Diccionario con campos de hr.contribution.form.line
            data: Diccionario con informacion relevante
        @return:
            None
        """
        pay_arl = new_line['main'] and not data['f_type'] == '12'
        new_line['arl_rate'] = new_line['arl_risk'] / 100 if pay_arl else 0
        new_line['arl_cot'] = new_line['arl_rate'] * new_line['arl_ibc']

        pay_ccf = new_line['main']
        pay_ccf |= data['hr_avancys.pay_ccf_mat_pat'] and new_line['lma']
        pay_ccf |= lp[1] == 'VAC'
        pay_ccf |= not new_line['main'] and (new_line['ret'] == 'X')
        pay_ccf &= not data['apr']
        new_line['ccf_rate'] = 0.04 if pay_ccf else 0
        new_line['ccf_cot'] = new_line['ccf_ibc'] * new_line['ccf_rate']

        pay_sena = new_line['global_ibc'] >= 10 * data['smmlv']
        pay_sena |= data['int']
        pay_sena &= not new_line['sln']
        new_line['sena_rate'], new_line['icbf_rate'] = (
            0.02, 0.03) if pay_sena else (0, 0)
        new_line['sena_cot'] = new_line['other_ibc'] * new_line['sena_rate']
        new_line['icbf_cot'] = new_line['other_ibc'] * new_line['icbf_rate']

    def get_dates(self, lp, new_line, data):
        """
        Agrega a new_line los valores de las fechas
        @params:
            lp: Tupla de 7 elementos (leave_id, 'type', amount, days, start, end, previuos_ibc)
            new_line: Diccionario con campos de hr.contribution.form.line
            data: Diccionario con informacion relevante
        @return:
            None
        """
        date_fields = ['sln_start', 'sln_end', 'ige_start', 'ige_end',
                       'lma_start', 'lma_end', 'vac_start', 'vac_end', 'atep_start', 'atep_end']
        for df in date_fields:
            leave, date = df.split('_')
            date = lp[4] if date == 'start' else lp[5]
            set_date = leave == 'sln' and lp[1] == 'NO_PAY'
            set_date |= leave == 'ige' and lp[1] == 'SICKNESS'
            set_date |= leave == 'lma' and lp[1] in ('MAT_LIC', 'PAT_LIC')
            set_date |= leave == 'vac' and lp[1] == 'VAC'
            set_date |= leave == 'atep' and lp[1] == 'AT_EP'
            new_line[df] = date if set_date else None

    def set_file_pila(self):
        for record in self:
            body = record.build_file()
            body = orm.remove_accents(body)
            body = orm.bytes2base64(body)
            record.write({'file_pila': body})

    def build_file(self):
        total_text = ''
        break_line = '\r\n'
        # ----- HEADER ----- #
        hl = [''] * (22 + 1)
        # 1: Tipo de registro
        hl[1] = '01'

        # 2: Modalidad de la planilla
        hl[2] = '1'

        # 3: Secuencia # TODO Está generando el 0001 pero se debe validar que siempre sea el mismo
        hl[3] = '0001'

        # 4: Nombre o razon social del aportante
        hl[4] = orm.prep_field(self.company_id.partner_id.name, size=200)

        # 5: Tipo de documento del aportante # TODO Asignado directamente tipo de documento NIT
        hl[5] = 'NI'

        # 6: Numero de identificacion del aportante
        hl[6] = orm.prep_field(self.company_id.partner_id.ref_num, size=16)

        # 7: Digito de verificacion
        hl[7] = str(self.company_id.partner_id.verification_code)

        # 8: Tipo de planilla
        hl[8] = 'E'

        # 9: Numero de la planilla asociada a esta planilla # TODO revisar casos de planillas N y F
        hl[9] = orm.prep_field(" ", size=10)

        # 10: Fecha de planilla de pago asociada a esta planilla
        hl[10] = orm.prep_field(" ", size=10)

        # 11: Forma de presentacion # TODO temporalmente forma de presentacion unica
        hl[11] = orm.prep_field('U', size=1)

        # 12: Codigo de sucursal # TODO referente campo 11
        hl[12] = orm.prep_field(self.branch_code, size=10)

        # 13: Nombre de la sucursal
        hl[13] = orm.prep_field(self.branch_code, size=40)

        # 14: Código de la ARL a la cual el aportante se encuentra afiliado

        hl[14] = orm.prep_field(self.company_id.arl_id.arl_code, size=6)

        # 15: Período de pago para los sistemas diferentes al de salud
        hl[15] = orm.prep_field(self.period_id.start, size=7)

        # 16: Período de pago para el sistema de salud.
        hl[16] = orm.prep_field(
            self.period_id.start + relativedelta(months=1), size=7)

        # 17: Número de radicación o de la Planilla Integrada de Liquidación de Aportes. (Asignado por el sistema)
        hl[17] = orm.prep_field(" ", size=10)

        # 18: Fecha de pago (aaaa-mm-dd) (Asignado por el siustema)
        hl[18] = orm.prep_field(" ", size=10)

        # 19: Numero total de empleados
        hl[19] = orm.prep_field(len(self.contracts_ids),
                                align='right', fill='0', size=5)

        # 20: Valor total de la nomina
        ibp_sum = sum([x.ccf_ibc for x in self.contribution_line_ids])
        hl[20] = orm.prep_field(int(ibp_sum), align='right', fill='0', size=12)

        # 21: Tipo de aportante
        hl[21] = orm.prep_field("1", size=2)

        # 22: Codigo de operador de informacion
        hl[22] = orm.prep_field(" ", size=2)

        for x in hl:
            total_text += x
        total_text += break_line

        # ----- BODY ----- #
        i, j = 0, len(self.contribution_line_ids)
        seq = 0
        for l in self.contribution_line_ids:
            seq += 1
            employee = l.contract_id.employee_id
            ref_type = employee.partner_id.ref_type_id.code
            bl = [''] * (98 + 1)
            # 1: Tipo de registro
            bl[1] = '02'
            # 2: Secuencia
            bl[2] = orm.prep_field(seq, align='right', fill='0', size=5)
            # 3: Tipo de documento de cotizante
            bl[3] = orm.prep_field(ref_type, size=2)
            # 4: Numero de identificacion cotizante
            bl[4] = orm.prep_field(employee.partner_id.ref_num, size=16)
            # 5: Tipo de cotizante
            bl[5] = orm.prep_field(l.contract_id.fiscal_type_id.code if l.contract_id.fiscal_type_id.code != '51' else '01',
                                   size=2)
            # 6: Subtipo de cotizante
            bl[6] = orm.prep_field(
                l.contract_id.fiscal_subtype_id.code or '00', size=2)
            # 7: Extranjero no obligado a cotizar pensiones
            foreign = False
            # foreign = employee.partner_id.country_id.code != 'CO' and ref_type in ('CE', 'PA', 'CD')
            bl[7] = 'X' if foreign else ' '
            # 8: Colombiano en el exterior
            is_col = True if ref_type in (
                'CC', 'TI') and employee.partner_id.country_id.code == 'CO' else False
            in_ext = False
            if l.contract_id.work_city_id:
                in_ext = True if l.contract_id.work_city_id.state_id.country_id.code != 'CO' else False
            bl[8] = 'X' if is_col and in_ext else ' '
            # 9: Código del departamento de la ubicación laboral
            bl[9] = orm.prep_field(
                l.contract_id.work_city_id.state_id.code, size=2)
            # 10: Código del municipio de ubicación laboral
            bl[10] = orm.prep_field(l.contract_id.work_city_id.zipcode, size=3)
            # 11: Primer apellido
            if employee.partner_id.first_name:
                pap = orm.remove_accents(
                    employee.partner_id.first_name.upper()).decode("utf-8").replace(".", "")
                bl[11] = orm.prep_field(pap, size=20)
            else:
                bl[11] = orm.prep_field(' ', size=20)
            # 12: Segundo apellido
            if employee.partner_id.second_name:
                sap = orm.remove_accents(
                    employee.partner_id.second_name.upper()).decode("utf-8").replace(".", "")
                bl[12] = orm.prep_field(sap, size=30)
            else:
                bl[12] = orm.prep_field(' ', size=30)
            # 13: Primer nombre
            if employee.partner_id.first_surname:
                pno = orm.remove_accents(
                    employee.partner_id.first_surname.upper()).decode("utf-8").replace(".", "")
                bl[13] = orm.prep_field(pno, size=20)
            else:
                bl[13] = orm.prep_field(' ', size=20)
            # 14: Segundo nombre
            if employee.partner_id.second_surname:
                sno = orm.remove_accents(
                    employee.partner_id.second_surname.upper()).decode("utf-8").replace(".", "")
                bl[14] = orm.prep_field(sno, size=30)
            else:
                bl[14] = orm.prep_field(' ', size=30)
            # 15: Ingreso
            bl[15] = 'X' if l.ing else ' '
            # 16: Retiro
            bl[16] = 'X' if l.ret else ' '
            # 17: Traslasdo desde otra eps
            bl[17] = 'X' if l.tde else ' '
            # 18: Traslasdo a otra eps
            bl[18] = 'X' if l.tae else ' '
            # 19: Traslasdo desde otra administradora de pensiones
            bl[19] = 'X' if l.tdp else ' '
            # 20: Traslasdo a otra administradora de pensiones
            bl[20] = 'X' if l.tap else ' '
            # 21: Variacion permanente del salario
            bl[21] = 'X' if l.vsp else ' '
            # 22: Correcciones
            bl[22] = 'X' if l.fixes else ' '
            # 23: Variacion transitoria del salario
            bl[23] = 'X' if l.vst else ' '
            # 24: Suspension temporal del contrato
            bl[24] = 'X' if l.sln else ' '
            # 25: Incapacidad temporal por enfermedad general
            bl[25] = 'X' if l.ige else ' '
            # 26: Licencia de maternidad o paternidad
            bl[26] = 'X' if l.lma else ' '
            # 27: Vacaciones, licencia remunerada
            bl[27] = l.vac_lr if l.vac_lr else ' '
            # 28: Aporte voluntario
            bl[28] = 'X' if l.avp else ' '
            # 29: Variacion de centro de trabajo
            bl[29] = 'X' if l.vct else ' '
            # 30: Dias de incapacidad por enfermedad laboral
            bl[30] = orm.prep_field("{:02.0f}".format(
                l.irl), align='right', fill='0', size=2)
            # 31: Codigo de la administradora de fondos de pensiones
            bl[31] = orm.prep_field(l.afp_code, size=6)
            # 32: Codigo de administradora de pensiones a la cual se traslada el afiliado #TODO
            bl[32] = orm.prep_field(l.afp_to_code, size=6)
            # 33: Codigo de EPS a la cual pertenece el afiliado
            bl[33] = orm.prep_field(l.eps_code, size=6)
            # 34: Codigo de eps a la cual se traslada el afiliado
            bl[34] = orm.prep_field(l.eps_to_code, size=6)
            # 35: Código CCF a la cual pertenece el afiliado
            bl[35] = orm.prep_field(l.ccf_code, size=6)
            # 36: Numero de dias cotizados a pension
            bl[36] = orm.prep_field("{:02.0f}".format(
                l.pens_days), align='right', fill='0', size=2)
            # 37: Numero de dias cotizados a salud
            bl[37] = orm.prep_field("{:02.0f}".format(
                l.eps_days), align='right', fill='0', size=2)
            # 38: Numero de dias cotizados a ARL
            bl[38] = orm.prep_field("{:02.0f}".format(
                l.arl_days), align='right', fill='0', size=2)
            # 39: Numero de dias cotizados a CCF
            bl[39] = orm.prep_field("{:02.0f}".format(
                l.ccf_days), align='right', fill='0', size=2)
            # 40: Salario basico
            bl[40] = orm.prep_field("{:09.0f}".format(
                l.wage), align='right', fill='0', size=9)
            # 41: Salario integral, resolucion 454
            bl[41] = l.wage_type
            # 42: IBC pension
            bl[42] = orm.prep_field("{:09.0f}".format(
                l.pens_ibc), align='right', fill='0', size=9)
            # 43: IBC salud
            bl[43] = orm.prep_field("{:09.0f}".format(
                l.eps_ibc), align='right', fill='0', size=9)
            # 44: IBC arl
            bl[44] = orm.prep_field("{:09.0f}".format(
                l.arl_ibc), align='right', fill='0', size=9)
            # 45: IBC CCF
            bl[45] = orm.prep_field("{:09.0f}".format(
                l.ccf_ibc), align='right', fill='0', size=9)
            # 46: Tarifa de aporte a pensiones
            bl[46] = orm.prep_field("{:01.5f}".format(
                l.pens_rate), align='right', fill='0', size=7)
            # 47: Cotizacion pension
            bl[47] = orm.prep_field("{:09.0f}".format(
                l.pens_cot), align='right', fill='0', size=9)
            # 48: Aportes voluntarios del afiliado
            bl[48] = orm.prep_field("{:09.0f}".format(
                l.ap_vol_contributor), align='right', fill='0', size=9)
            # 49: Aportes voluntarios del aportante
            bl[49] = orm.prep_field("{:09.0f}".format(
                l.ap_vol_company), align='right', fill='0', size=9)
            # 50: Total cotizacion pensiones
            bl[50] = orm.prep_field("{:09.0f}".format(
                l.pens_total), align='right', fill='0', size=9)
            # 51: Aportes a fondo solidaridad
            bl[51] = orm.prep_field("{:09.0f}".format(
                l.fsol), align='right', fill='0', size=9)
            # 52: Aportes a fondo subsistencia
            bl[52] = orm.prep_field("{:09.0f}".format(
                l.fsub), align='right', fill='0', size=9)
            # 53: Valor no retenido por aportes voluntarios
            bl[53] = orm.prep_field("{:09.0f}".format(
                l.ret_cont_vol), align='right', fill='0', size=9)
            # 54: Tarifa de aportes salud
            bl[54] = orm.prep_field("{:01.5f}".format(
                l.eps_rate), align='right', fill='0', size=7)
            # 55: Aportes salud
            bl[55] = orm.prep_field("{:09.0f}".format(
                l.eps_cot), align='right', fill='0', size=9)
            # 56: Total UPS adicional
            bl[56] = orm.prep_field("{:09.0f}".format(
                l.ups), align='right', fill='0', size=9)
            # 57: Numero de autorizacion de incapacidad
            bl[57] = orm.prep_field(l.aus_auth, size=15)
            # 58: Valor de la incapacidad por enf general
            bl[58] = orm.prep_field("{:09.0f}".format(
                l.gd_amount), align='right', fill='0', size=9)
            # 59: Numero de autorizacion por licencia de maternidad
            bl[59] = orm.prep_field(l.mat_auth, size=15)
            # 60: Valor de licencia de maternidad
            bl[60] = orm.prep_field("{:09.0f}".format(
                l.mat_amount), align='right', fill='0', size=9)
            # 61: Tarifa de aportes a riesgos laborales
            bl[61] = orm.prep_field("{:01.5f}".format(
                l.arl_rate), align='right', fill='0', size=9)
            # 62: Centro de trabajo
            bl[62] = orm.prep_field(
                l.work_center, align='right', fill='0', size=9)
            # 63: Cotizacion obligatoria a riesgos laborales
            bl[63] = orm.prep_field("{:09.0f}".format(
                l.arl_cot), align='right', fill='0', size=9)
            # 64: Tarifa de aportes CCF
            bl[64] = orm.prep_field("{:01.5f}".format(
                l.ccf_rate), align='right', fill='0', size=7)
            # 65: Aportes CCF
            bl[65] = orm.prep_field("{:09.0f}".format(
                l.ccf_cot), align='right', fill='0', size=9)
            # 66: Tarifa SENA
            bl[66] = orm.prep_field("{:01.5f}".format(
                l.sena_rate), align='right', fill='0', size=7)
            # 67: Aportes SENA
            bl[67] = orm.prep_field("{:09.0f}".format(
                l.sena_cot), align='right', fill='0', size=9)
            # 68: Tarifa ICBF
            bl[68] = orm.prep_field("{:01.5f}".format(
                l.icbf_rate), align='right', fill='0', size=7)
            # 69: Aportes ICBF
            bl[69] = orm.prep_field("{:09.0f}".format(
                l.icbf_cot), align='right', fill='0', size=9)
            # 70: Tarifa ESAP
            bl[70] = orm.prep_field("{:01.5f}".format(
                l.esap_rate), align='right', fill='0', size=7)
            # 71: Aportes ESAP
            bl[71] = orm.prep_field("{:09.0f}".format(
                l.esap_cot), align='right', fill='0', size=9)
            # 72: Tarifa MEN
            bl[72] = orm.prep_field("{:01.5f}".format(
                l.men_rate), align='right', fill='0', size=7)
            # 73: Aportes MEN
            bl[73] = orm.prep_field("{:09.0f}".format(
                l.men_cot), align='right', fill='0', size=9)
            # 74: Tipo de documento del cotizante principal
            bl[74] = orm.prep_field(' ', size=2)
            # 75: Numero de documento de cotizante principal
            bl[75] = orm.prep_field(' ', size=16)
            # 76: Exonerado de aportes a paraficales y salud
            bl[76] = 'S' if l.exonerated else 'N'
            # 77: Codigo de la administradora de riesgos laborales
            bl[77] = orm.prep_field(l.arl_code, size=6)
            # 78: Clase de riesgo en la cual se encuentra el afiliado
            bl[78] = orm.prep_field(l.arl_risk, size=1)
            # 79: Indicador de tarifa especial de pensiones
            bl[79] = orm.prep_field(' ', size=1)
            # 80: Fecha de ingreso
            bl[80] = orm.prep_field(l.k_start, size=10)
            # 81: Fecha de retiro
            bl[81] = orm.prep_field(l.k_end, size=10)
            # 82: Fecha de inicio de VSP
            bl[82] = orm.prep_field(l.vsp_start, size=10)
            # 83: Fecha de inicio SLN
            bl[83] = orm.prep_field(l.sln_start, size=10)
            # 84: Fecha de fin SLN
            bl[84] = orm.prep_field(l.sln_end, size=10)
            # 85: Fecha de inicio IGE
            bl[85] = orm.prep_field(l.ige_start, size=10)
            # 86: Fecha de fin IGE
            bl[86] = orm.prep_field(l.ige_end, size=10)
            # 87: Fecha de inicio LMA
            bl[87] = orm.prep_field(l.lma_start, size=10)
            # 88: Fecha de fin LMA
            bl[88] = orm.prep_field(l.lma_end, size=10)
            # 89: Fecha de inicio VAC
            bl[89] = orm.prep_field(l.vac_start, size=10)
            # 90: Fecha de fin VAC
            bl[90] = orm.prep_field(l.vac_end, size=10)

            bl[91] = orm.prep_field(l.vct_start, size=10)
            bl[92] = orm.prep_field(l.vct_end, size=10)
            # 93: Fecha de inicio ATEP
            bl[93] = orm.prep_field(l.atep_start, size=10)
            # 94: Fecha de fin ATEP
            bl[94] = orm.prep_field(l.atep_end, size=10)
            # 95: IBC otros parafiscales
            bl[95] = orm.prep_field("{:09.0f}".format(
                l.other_ibc), align='right', fill='0', size=9)

            # 96: Numero de horas laboradas
            bl[96] = orm.prep_field("{:03.0f}".format(
                l.w_hours), align='right', fill='0', size=3)

            bl[97] = orm.prep_field('', size=10)

            i += 1
            for x in bl:
                total_text += x
            total_text += break_line

        return total_text
