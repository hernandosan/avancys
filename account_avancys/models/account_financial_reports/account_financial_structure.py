# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountFinancialStructure(models.Model):
    _name = 'account.financial.structure'

    name = fields.Char(
        string='Nombre',
    )
    is_active = fields.Boolean(
        string='Activo',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañia',
        default=lambda self: self.env.company,
    )
    line_ids = fields.One2many(
        comodel_name='account.financial.structure.line',
        inverse_name='structure_id',
        string='Estructura',
    )

class AccountFinancialStructureLine(models.Model):
    _name = 'account.financial.structure.line'

    structure_id = fields.Many2one(
        comodel_name='account.financial.structure',
        string='Estructura',
    )
    digits = fields.Integer(
        string='Digitos',
    )
    sequence = fields.Integer(
        string='Secuenca',
    )
    description = fields.Char(
        string='Descripción',
    )

class AccountFinancialLevels(models.Model):
    _name = 'account.financial.levels'

    code = fields.Char(
        string='Código',
    )
    name = fields.Char(
        string='Nombre',
    )
    help = fields.Char(
        string='Ayuda',
    )