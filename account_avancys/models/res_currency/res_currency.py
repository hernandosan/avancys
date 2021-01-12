# -*- coding: utf-8 -*-

from odoo import api, fields, models

class ResCurrency(models.Model):
    _inherit = 'res.currency'

    def _get_rate(self, company, date):
        query = """SELECT rate
                   FROM res_currency_rate
                   WHERE name = %s
                   AND company_id = %s
                   LIMIT 1"""
        self._cr.execute(query, (date, company.id))
        currency_rates = self._cr.fetchone()
        return currency_rates