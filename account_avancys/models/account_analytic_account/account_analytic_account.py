# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    city_id = fields.Many2one('res.city', string='Ciudad')
