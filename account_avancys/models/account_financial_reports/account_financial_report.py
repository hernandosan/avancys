# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountFinancialReportTrial(models.Model):
    _name = 'account.financial.report.trial'

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañia',
    )
    date = fields.Date(
        string='Fecha',
    )
    date_start = fields.Date(
        string='Fecha Inicio',
    )
    date_end = fields.Date(
        string='Fecha Fin',
    )
    line_ids = fields.One2many(
        comodel_name='account.financial.report.trial.line',
        inverse_name='report_trial_id',
        string='Lineas Informe',
    )


class AccountFinancialReportTrialLine(models.Model):
    _name = 'account.financial.report.trial.line'

    report_trial_id = fields.Many2one(
        comodel_name='account.financial.report.trial',
        string='Informe',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
    )
    bold = fields.Boolean(
        string='Negrilla',
    )
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Tercero',
    )
    code = fields.Char(
        string='Code',
    )
    name = fields.Char(
        string='Nombre Cuenta'
    )
    amount_initial = fields.Float(
        string='Saldo Inicial',
    )
    debit = fields.Float(
        string='Debito',
    )
    credit = fields.Float(
        string='Credito',
    )
    amount_final = fields.Float(
        string='Saldo Final',
    )
    level = fields.Integer(
        string='Nivel',
    )

class AccountFinancialReportBalance(models.Model):
    _name = 'account.financial.report.balance'

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañia',
    )
    date = fields.Date(
        string='Fecha',
    )
    date_start = fields.Date(
        string='Fecha Inicio',
    )
    date_end = fields.Date(
        string='Fecha Fin',
    )
    line_ids = fields.One2many(
        comodel_name='account.financial.report.balance.line',
        inverse_name='report_balance_id',
        string='Lineas Informe',
    )

class AccountFinancialReportBalanceLine(models.Model):
    _name = 'account.financial.report.balance.line'

    report_balance_id = fields.Many2one(
        comodel_name='account.financial.report.balance',
        string='Informe',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
    )
    bold = fields.Boolean(
        string='Negrilla',
    )
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Tercero',
    )
    code = fields.Char(
        string='Code',
    )
    name = fields.Char(
        string='Nombre Cuenta'
    )
    amount_initial = fields.Float(
        string='Saldo Inicial',
    )
    debit = fields.Float(
        string='Debito',
    )
    credit = fields.Float(
        string='Credito',
    )
    amount_final = fields.Float(
        string='Saldo Final',
    )
    level = fields.Integer(
        string='Nivel',
    )


class AccountFinancialReportTaxes(models.Model):
    _name = 'account.financial.report.taxes'

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañia',
    )
    user_id = fields.Many2one(
        comodel_name='res.uers',
        string='Usuario',
    )
    date = fields.Date(
        string='Fecha',
    )
    date_from = fields.Date(
        string='Fecha Inicial',
    )
    date_to = fields.Date(
        string='Fecha Final',
    )

class AccountFinancialReportTaxesLine(models.Model):
    _name = 'account.financial.report.taxes.line'

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañia',
    )
    user_id = fields.Many2one(
        comodel_name='res.uers',
        string='Usuario',
    )
    report_tax_id = fields.Many2one(
        comodel_name='account.financial.report.taxes',
        string='Encabezado',
    )
    bold = fields.Boolean(
        string='bold',
    )
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta',
    )
    account = fields.Char(
        string='Código',
    )
    account_analytic_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string='Cuenta Analitica',
    )
    account_tax_id = fields.Many2one(
        comodel_name='account.tax',
        string='Impuestos',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Tercero',
    )
    date = fields.Date(
        string='Fecha',
    )
    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Movimiento',
    )
    move_line_id = fields.Many2one(
        comodel_name='account.move.line',
        string='Linea Contable',
    )
    debit = fields.Float(
        string='Debito',
    )
    credit = fields.Float(
        string='Credito',
    )
    amount_final = fields.Float(
        string='Saldo Final',
    )
    base_amount = fields.Float(
        string='Base',
    )
    tax_amount = fields.Float(
        string='Retención',
    )

