# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ciiu_ica = fields.Boolean(
        string="Ciiu en ICA",
        config_parameter='account_avancys.ciiu_ica',
        default=False)
    city_cc = fields.Boolean(
        string="Ciudades en cuentas analíticas",
        config_parameter='account_avancys.city_cc',
        default=False)
