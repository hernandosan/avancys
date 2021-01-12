# -*- coding: utf-8 -*-
from odoo import api, fields, models

LAST_ONE = -1


class SeveranceUpdateHistory(models.Model):
    _name = 'severance.update.history'
    _order = 'date desc'
    _rec_name = "date"
    _description = 'Histórico de Cambios de Fondo de Cesantías'

    contract_id = fields.Many2one(
        string='Contrato', comodel_name='hr.contract', required=True)
    afp_severance_id = fields.Many2one(
        string='Fondo de Cesantías', comodel_name='res.partner',
        domain="[('afp','=','True')]", required=True)
    date = fields.Date(
        string='Fecha', efault=fields.Date.today(), required=True)
    user_id = fields.Many2one(string='Responsable', comodel_name='res.users',
                              default=lambda self: self.env.user,
                              required=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.company,
        index=True, required=True)

    @api.model
    def create(self, vals):
        res = super(SeveranceUpdateHistory, self).create(vals)
        contract_id = vals.get('contract_id', False)
        histories = self.search([('contract_id', '=', contract_id)]).sorted(
            lambda hist: hist.date)
        afp_severance_id = (histories[LAST_ONE].afp_severance_id.id
                            if histories
                            else vals.get('afp_severance_id', False))
        self.env['hr.contract'].browse([contract_id]).write(
            {'afp_severance_id': afp_severance_id})
        return res
