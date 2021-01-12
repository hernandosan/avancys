# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    partner_id = fields.Many2one(
        comodel_name='res.partner', string='Account Holder',
        ondelete='cascade', index=True,
        domain="[('company_id', '=', company_id)]", required=True)
