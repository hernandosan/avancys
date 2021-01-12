# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

CATEGORY_PAYSLIP = [
    ('earnings', 'DEVENGADO'),
    ('o_salarial_earnings', 'OTROS DEVENGOS SALARIALES'),
    ('comp_earnings', 'INGRESOS COMPLEMENTARIOS'),
    ('o_rights', 'OTROS DERECHOS'),
    ('o_earnings', 'OTROS DEVENGOS'),
    ('non_taxed_earnings', 'INGRESOS NO GRAVADOS'),
    ('deductions', 'DEDUCCIONES'),
    ('contributions', 'APORTES'),
    ('provisions', 'PROVISIONES'),
    ('subtotals', 'SUBTOTALES'),
]

PARTNER_TYPE = [
    ('EPS', 'EPS'),
    ('ARL', 'ARL'),
    ('CES', 'CESANTIAS'),
    ('PEN', 'PENSIONES'),
    ('CCF', 'CAJA DE COMPENSACION FAMILIAR'),
    ('OTHER', 'OTRO')
]


class ModelBasicPayslipNoveltyType(models.AbstractModel):
    _name = 'model.basic.payslip.novelty.type'
    _description = 'model.basic.payslip.novelty.type'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código', required=True)
    category = fields.Selection(
        string="Categoría", selection=CATEGORY_PAYSLIP, required=True)
    partner_type = fields.Selection(
        string='Tipo de tercero', selection=PARTNER_TYPE)
    partner_id = fields.Many2one(comodel_name='res.partner', string='Tercero')
    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company)

    reg_adm_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Regular Administrativo')
    int_adm_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Integral Administrativo')
    apr_adm_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Aprendiz Administrativo')
    reg_com_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Regular Comercial')
    int_com_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Integral Comercial')
    apr_com_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Aprendiz Comercial')
    reg_ope_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Regular Operativa')
    int_ope_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Integral Operativa')
    apr_ope_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Aprendiz Operativa')
    reg_pro_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Regular  Producción')
    int_pro_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Integral Producción')
    apr_pro_debit = fields.Many2one(
        comodel_name='account.account', string='Debito Aprendiz Producción')

    reg_adm_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Regular Administrativo')
    int_adm_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Integral Administrativo')
    apr_adm_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Aprendiz Administrativo')
    reg_com_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Regular Comercial')
    int_com_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Integral Comercial')
    apr_com_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Aprendiz Comercial')
    reg_ope_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Regular Operativa')
    int_ope_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Integral Operativa')
    apr_ope_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Aprendiz Operativa')
    reg_pro_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Regular  Producción')
    int_pro_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Integral Producción')
    apr_pro_credit = fields.Many2one(
        comodel_name='account.account', string='Credito Aprendiz Producción')

    _sql_constraints = [
        ("code_uniq", "unique (code)", "El Código debe ser único por categoría")
    ]
