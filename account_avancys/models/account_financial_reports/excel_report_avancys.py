# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class ExcelReportAvancys(models.TransientModel):
    _name = "excel.report.avancys"

    excel_file = fields.Binary('Reporte Excel')
    file_name = fields.Char('Archivo Excel', size=64)