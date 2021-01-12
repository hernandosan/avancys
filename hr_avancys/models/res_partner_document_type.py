# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResPartnerDocumentType(models.Model):
    _name = 'res.partner.document.type'
    _description = 'Tipo de identificación'
    _order = 'name'

    name = fields.Char(string='Nombre')
    code = fields.Char(string='Código')
    code_dian = fields.Char(string='Código DIAN')

    _sql_constraints = [
        ("code_uniq", "unique (code)", "El código del tipo de documento debe ser unico")
    ]
