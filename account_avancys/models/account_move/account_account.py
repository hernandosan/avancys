# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class AccountAccount(models.Model):
    _inherit = 'account.account'
