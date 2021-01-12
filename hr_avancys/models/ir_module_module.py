# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.addons import hr_avancys


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    @api.model
    def hook_to_upgrade(self):
        hr_avancys.pre_init_hook(self._cr)
        hr_avancys.post_init_hook(self._cr, False)
