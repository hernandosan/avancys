# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.addons import hr_avancys


class ResCompany(models.Model):
    _inherit = 'res.company'

    arl_id = fields.Many2one(
        comodel_name='res.partner', string='ARL', domain="[('arl','=','True')]")
