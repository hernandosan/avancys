# -*- coding: utf-8 -*-
from odoo import api, fields, models

LAST_ONE = -1


class WageUpdateHistory(models.Model):
    _name = 'wage.update.history'
    _order = 'date desc'
    _rec_name = "date"
    _description = 'Histórico de Cambios de Salario'

    contract_id = fields.Many2one(
        string='Contrato', comodel_name='hr.contract', required=True)
    wage = fields.Float(
        string='Salario', required=True)
    date = fields.Date(
        string='Fecha', default=fields.Date.today(), required=True)
    user_id = fields.Many2one(string='Responsable', comodel_name='res.users',
                              default=lambda self: self.env.user,
                              required=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.company,
        index=True, required=True)

    @api.model
    def create(self, vals):
        res = super(WageUpdateHistory, self).create(vals)
        contract_id = vals.get('contract_id', False)
        histories = self.search([('contract_id', '=', contract_id)]).sorted(
            lambda hist: hist.date)
        wage = (histories[LAST_ONE].wage
                          if histories
                          else vals.get('wage', 0.0))
        self.env['hr.contract'].browse([contract_id]).write(
            {'wage': wage})
        return res
