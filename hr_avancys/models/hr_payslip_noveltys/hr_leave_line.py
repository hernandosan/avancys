# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.addons.avancys_tools import orm

STATE = [
    ('validated', 'Validada'),
    ('paid', 'Pagada')
]


class HrLeaveLine(models.Model):
    _name = 'hr.leave.line'
    _description = 'Lineas de Ausencia'

    leave_id = fields.Many2one(
        comodel_name='hr.leave', string='Ausencia', required=True)
    payslip_id = fields.Many2one(comodel_name='hr.payslip', string='Nónima')
    contract_id = fields.Many2one(
        string="Contrato", related='leave_id.contract_id')
    date = fields.Date(string='Fecha')
    period_id = fields.Many2one(comodel_name='hr.period', string='Periodo')
    state = fields.Selection(string='Estado', selection=STATE)
    amount = fields.Float(string='Valor')
    sequence = fields.Integer(string='Secuencia')

    def create_payslip_line(self, payslip_id):
        leave_type_id = self.leave_id.leave_type_id
        rate, concept_id = leave_type_id.get_rate_concept_id(self.sequence)
        payslip_line = {
            'name': leave_type_id.name,
            'payslip_id': payslip_id,
            'category': leave_type_id.category,
            'value': self.amount,
            'qty': 1 if leave_type_id.category_type != 'VAC_MONEY' else self.leave_id.days_vac_money,
            'rate': rate,
            'total': self.amount,
            'origin': 'local',
            'concept_id': concept_id,
            'leave_id': self.leave_id.id,
            'novelty_id': None,
            'overtime_id': None,
        }
        for unique_key in ['rate', 'concept_id', 'leave_id', 'novelty_id', 'overtime_id']:
            if 'unique_key' in payslip_line:
                payslip_line['unique_key'] += str(payslip_line[unique_key])
            else:
                payslip_line['unique_key'] = str(payslip_line[unique_key])
        return payslip_line

    def belongs_category(self, categories):
        return self.leave_id.leave_type_id.id in categories

    def get_info_from_leave_type(self, cr, data):
        """
        Obtiene el numero de dias de un tipo de ausencia y de un contrato
        @params:
        cr: cursor con el que se va a ejecutar la consulta
        data: diccionario con la siguiente estructura.
            {'contract':int, 'start':datetime, 'end':datetime,'type':tuple(string)}
        """
        query = """
        SELECT COUNT(*), SUM(HLL.amount)
        FROM hr_leave_line AS  HLL
        INNER JOIN hr_leave AS HL ON HL.id = HLL.leave_id
        INNER JOIN hr_leave_type AS HLT ON HLT.id = HL.leave_type_id
        WHERE
            HL.contract_id = %(contract)s AND
            HLL.date BETWEEN %(start)s AND %(end)s AND
            HLT.category_type in %(type)s
        """
        res = orm._fetchall(cr, query, data)
        return sum([x[0] for x in res if x[0]]), sum([x[1] for x in res if x[1]])
