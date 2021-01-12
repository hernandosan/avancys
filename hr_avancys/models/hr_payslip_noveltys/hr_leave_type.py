# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

CATEGORY_TYPE = [
    ('SICKNESS', 'Incapacidad de enfermedad general'),
    ('MAT_LIC', 'Licencia de maternidad'),
    ('PAT_LIC', 'Licencia de paternidad'),
    ('AT_EP', 'Accidente de trabajo - Enfermedad profesional'),
    ('NO_PAY', 'Sin paga'),
    ('PAY', 'Con Paga'),
    ('VAC', 'Vacaciones'),
    ('VAC_MONEY', 'Vacaciones en dinero')
]


class HrLeaveType(models.Model):
    _name = 'hr.leave.type'
    _inherit = 'model.basic.payslip.novelty.type'
    _description = 'Categoría de Ausencias'
    _order = 'name'

    category_type = fields.Selection(
        string='Tipo', selection=CATEGORY_TYPE, required=True)

    b2 = fields.Float(string='De 1 a 2 días')
    b90 = fields.Float(string='De 3 a 90 días')
    b180 = fields.Float(string='De 91 a 180 días')
    a180 = fields.Float(string='De 181 días en adelante')

    apply_day_31 = fields.Boolean(string='Aplica día 31')
    discount_rest_day = fields.Boolean(string='Descontar día de descanso')

    def get_rate_concept_id(self, sequence):
        concept = self.env['hr.concept']
        if self.category_type != 'SICKNESS':
            rate = 100
            concept_id = None
        elif 1 <= sequence <= 2:
            rate = self.b2
            concept_id = concept.search([('code', '=', 'EG_B2')], limit=1).id
        elif 3 <= sequence <= 90:
            rate = self.b90
            concept_id = concept.search([('code', '=', 'EG_B90')], limit=1).id
        elif 91 <= sequence <= 180:
            rate = self.b180
            concept_id = concept.search([('code', '=', 'EG_B180')], limit=1).id
        elif 181 <= sequence:
            rate = self.a180
            concept_id = concept.search([('code', '=', 'EG_A180')], limit=1).id
        else:
            rate = 0
            concept_id = None
        return rate, concept_id or None

    def get_politics_leave(self):
        politics = {}
        if self.category_type == 'SICKNESS':
            param = 'hr_avancys.pays_eg_b2_with_wage'
            model = 'ir.config_parameter'
            politics[param] = (bool)(self.env[model].sudo().get_param(param))
        elif self.category_type == 'AT_EP':
            param = 'hr_avancys.pays_atep_b1_with_wage'
            model = 'ir.config_parameter'
            politics[param] = (bool)(self.env[model].sudo().get_param(param))
        return politics
