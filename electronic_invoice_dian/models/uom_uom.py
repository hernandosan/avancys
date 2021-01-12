# -*- coding: utf-8 -*-
from openerp import models, fields, api


class UomUom(models.Model):
    _inherit = 'uom.uom'

    code_dian = fields.Char(string='Código DIAN')
