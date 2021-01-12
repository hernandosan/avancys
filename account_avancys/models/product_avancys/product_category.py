# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductCategory(models.Model):
    _inherit = 'product.category'

    taxes_id = fields.Many2many('account.tax', 'product_category_taxes_rel', 'product_category_id', 'tax_id', 'Impuestos Cliente', domain=[('type_tax_use','in',['sale','none'])])
    supplier_taxes_id = fields.Many2many('account.tax', 'product_category_supplier_taxes_rel', 'product_category_id', 'tax_id', 'Impuestos Proveedor', domain=[('type_tax_use','in',['purchase','none'])])
    