# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pays_sub_trans_train_prod = fields.Boolean(
        string="Paga subsidio de transporte a aprendices en etapa productiva",
        config_parameter='hr_avancys.pays_sub_trans_train_prod',
        default=False)
    eps_rate_employee = fields.Float(
        string='EPS para empleado',
        config_parameter='hr_avancys.eps_rate_employee')
    eps_rate_employer = fields.Float(
        string='EPS para empleador',
        config_parameter='hr_avancys.eps_rate_employer')
    pen_rate_employee = fields.Float(
        string='Pensión para empleado',
        config_parameter='hr_avancys.pen_rate_employee')
    pen_rate_employer = fields.Float(
        string='Pensión para empleador',
        config_parameter='hr_avancys.pen_rate_employer')
    pays_eg_b2_with_wage = fields.Boolean(
        string="Paga 1-2 dias de incapacidad de enfermedad general con salario",
        config_parameter='hr_avancys.pays_eg_b2_with_wage',
        default=False)
    pays_atep_b1_with_wage = fields.Boolean(
        string="Paga 1 dia de accidente de trabajo - anfermedad profesional con salario",
        config_parameter='hr_avancys.pays_atep_b1_with_wage',
        default=False)
    discount_suspensions = fields.Boolean(
        string="Descuenta días de suspensión en prima",
        config_parameter='hr_avancys.discount_suspensions',
        default=False)
    average_sub_trans = fields.Boolean(
        string="Promediar subsidio de transporte en prestaciones sociales",
        config_parameter='hr_avancys.average_sub_trans',
        default=False)
    pay_ccf_mat_pat = fields.Boolean(
        string="Cotiza CCF en licencias de MAT o PAT",
        config_parameter='hr_avancys.pay_ccf_mat_pat',
        default=False)
