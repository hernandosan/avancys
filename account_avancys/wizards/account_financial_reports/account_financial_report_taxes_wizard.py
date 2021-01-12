# -*- coding: utf-8 -*-
from odoo import api, fields, models
import xlwt
import base64
import io
from odoo.exceptions import UserError
from datetime import datetime
import time


class AccountFinancialReportTaxesWizard(models.TransientModel):
    _name = 'account.financial.report.taxes.wizard'

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañia',
    )
    user_id = fields.Many2one(
        comodel_name='res.user',
        string='Usuario',
    )
    structure_id = fields.Many2one(
        comodel_name='account.financial.structure', 
        string='Plan Contable',
    )
    date_from = fields.Date(
        string='Fecha Inical',
        default=fields.Date.today(),
    )
    date_to = fields.Date(
        string='Fecha Final',
        default=fields.Date.today(),
    )
    account_ids = fields.Many2many(
        comodel_name='account.account',
        relation='report_taxes_accounts_rel',
        string='Cuentas',
        domain=[('internal_type', '!=', 'view')],
    )
    partner_ids = fields.Many2many(
        comodel_name='res.partner',
         relation='report_taxes_partners_rel',
        string='Terceros',
    )
    report_type = fields.Selection(
        string="Tipo de Reporte",
        selection=[
            ('excel', 'Excel'),
            ('pdf', 'PDF'),
        ],
        default='excel',
    )
    target_move = fields.Selection(
        selection=[
            ('draft', 'Movimientos En Borrador'),
            ('posted', 'Movimientos Asentados'),
            ('all', 'Todos los movimientos'),
        ],
        string='Movimientos', 
        required=True, 
        default='posted'
    )

    def _get_lines(self):
        user_id = self.env.user.id
        company_id = self.env.company.id
        # WHERE CONDITION
        where = 'AND aml.company_id = {company_id}'.format(company_id=company_id)
        if self.partner_ids:
            where += ' AND aml.partner_id in (%s)' % (','.join(str(x.id) for x in self.partner_ids))
        if self.account_ids:
            where += ' AND aml.account_id in (%s)' % (','.join(str(x.id) for x in self.account_ids))
        where_move = ''
        if self.target_move == 'posted':
            where_move += "AND am.state = 'posted'"
        elif self.target_move == 'draft':
            where_move += "AND am.state = 'draft'"
        
        # INSERT REPORT HEADER
        insert_header_query = (
            """
            INSERT INTO account_financial_report_taxes (company_id, user_id, date) VALUES ({company_id}, {user_id},'{date}') 
            RETURNING ID
            """.format(company_id=company_id,
                        user_id=user_id,
                        date=str(datetime.now())[:10])
        )
        self.env.cr.execute(insert_header_query)
        report_id = self.env.cr.fetchone()[0]
        
        # INSERT LINES REPORT
        insert_lines_query = (
            """
            INSERT INTO 
                account_financial_report_taxes_line (
                    bold, 
                    user_id, 
                    company_id, 
                    account_id, 
                    account, 
                    account_analytic_id, 
                    date, 
                    partner_id,
                    debit,
                    credit,
                    amount_final,
                    base_amount,
                    report_tax_id,
                    move_id,
                    account_tax_id
                )
            SELECT
                False,
                {user_id},
                {company_id},
                aml.account_id,
                aa.code,
                aml.analytic_account_id,
                aml.date,
                aml.partner_id,
                SUM(aml.debit) AS debit,
                SUM(aml.credit) AS credit,
                SUM(aml.debit-aml.credit) AS amount_final,
                SUM(COALESCE(aml.tax_base_amount,0)) AS base_amount,
                {report_id},
                aml.move_id,
                aml.tax_line_id
            FROM 
                account_move_line AS aml
            INNER JOIN 
                account_account AS aa ON aa.id = aml.account_id 
            INNER JOIN
                account_move as am on am.id = aml.move_id
            WHERE 
                aml.date >= '{date_from}' 
            AND 
                aml.date <= '{date_to}'
            AND
                aml.tax_line_id IS NOT NULL
            {where}
            {where_move}
            GROUP BY 
                aml.account_id,
                aml.partner_id,
                aml.analytic_account_id,
                aa.code,
                aml.date,
                aml.tax_line_id,
                aml.move_id
            """.format(user_id=user_id,
                       company_id=company_id,
                       report_id=report_id,
                       date_from=str(self.date_from),
                       date_to=str(self.date_to),
                       where=where,
                       where_move=where_move)
        )
        self.env.cr.execute(insert_lines_query)    

        # SELECT INFO
        query_select_lines = (
            """
            SELECT 
                afrtl.account AS account,
                aa.name AS account_name,
                rp.ref_num AS reference,
                rp.name AS partner_name,
                am.name AS move_name,
                afrtl.date AS date,
                aaa.name AS account_analytic_name,
                afrtl.debit AS debit,
                afrtl.credit AS credit,
                afrtl.amount_final AS amount_final
            FROM 	
                account_financial_report_taxes_line AS afrtl
            INNER JOIN
                account_account AS aa ON aa.id = afrtl.account_id
            INNER JOIN
                account_move AS am ON am.id = afrtl.move_id 
            INNER JOIN 	
                res_partner AS rp ON rp.id = afrtl.partner_id
            LEFT JOIN
                account_analytic_account AS aaa ON aaa.id = afrtl.account_analytic_id
            WHERE 
                afrtl.report_tax_id = {report_id}
            AND
                afrtl.company_id = {company_id}
            AND
                afrtl.user_id = {user_id}
            ORDER BY
                aa.code ASC
            """.format(report_id=report_id,
                       company_id=company_id,
                       user_id=user_id)
        )
        self.env.cr.execute(query_select_lines)
        results = self.env.cr.dictfetchall()

        lines_res = []
        for result in results:
            res = dict()
            res['code'] = result.get('account')
            res['name'] = result.get('account_name')
            res['reference'] = result.get('reference')
            res['partner_name'] = result.get('partner_name')
            res['move_name'] = result.get('move_name')
            res['date'] = result.get('date')
            res['account_analytic_name'] = result.get('account_analytic_name')
            res['debit'] = result.get('debit')
            res['credit'] = result.get('credit')
            res['amount_final'] = result.get('amount_final')
            lines_res.append(res)
        return lines_res
    
    def print_report_taxes(self):
        if self.date_from > self.date_to:
            raise UserError('La fecha final no puede ser inferior a la inicial')
        lines_res = self._get_lines()
        return self._print_report_taxes_excel(lines_res)
    
    def _print_report_taxes_excel(self,report_lines):
        company_id = self.env.company
        user = self.env.user
        date = datetime.now()
        filename = 'REPORTE_IMPUESTOS' + '_' + company_id.name + '_' + user.name + '_' + str(date)[:10] + '.xls'
        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet('Hoja 1')
        date_format = xlwt.XFStyle()
        date_format.num_format_str = 'dd/mm/yyyy'
        style_header = xlwt.easyxf(
            "font:height 300; font: name Liberation Sans, bold on,color black; align: horiz center")
        style_header_line = xlwt.easyxf(
            "font: name Liberation Sans, bold on,color black; align: horiz center")
        ##### STYLE BLUE 2 #####
        style_header_line_blue = xlwt.easyxf(
            "font: name Liberation Sans, bold on,color black; align: horiz center")
        xlwt.add_palette_colour("blue_2", 0x21)
        workbook.set_colour_RGB(0x21, 46, 134, 193)
        pattern = xlwt.Pattern()
        pattern.pattern = xlwt.Pattern.SOLID_PATTERN
        pattern.pattern_fore_colour = xlwt.Style.colour_map['blue_2']
        style_header_line_blue.pattern = pattern
        ##### ./STYLE BLUE 2 #####
        style_line = xlwt.easyxf(
            "font:bold on,color black;")
        style_line.num_format_str = '$#,##0.00'
        style_line_2 = xlwt.easyxf("align: horiz right;")
        currency_format = xlwt.XFStyle()
        currency_format.num_format_str = '$#,##0.00'
        worksheet.row(0).height_mismatch = True
        worksheet.row(0).height = 500
        # HEADER
        worksheet.write_merge(0, 0, 0, 5, self.env['res.users'].browse(self.env.uid).company_id.name + " : Reporte Auxiliar Impuestos", style=style_header)
        worksheet.write(2,0,'Desde:', style_header_line)
        worksheet.write(2,1,self.date_from,date_format)
        worksheet.write(2,2,'Hasta:', style_header_line)
        worksheet.write(2,3,self.date_to,date_format)
        worksheet.write(3,0,'Estado:', style_header_line)
        worksheet.write(4,0,'Fecha de Impresión:', style_header_line)
        worksheet.write(4,1,str(datetime.now()))
        # EXCEL FIELDS
        worksheet.write(6,0,'Codigo', style_header_line_blue)
        worksheet.write(6,1,'Cuenta', style_header_line_blue)
        worksheet.write(6,2,'Referencia', style_header_line_blue)
        worksheet.write(6,3,'Tercero', style_header_line_blue)
        worksheet.write(6,4,'Asiento', style_header_line_blue)
        worksheet.write(6,5,'Fecha', style_header_line_blue)
        worksheet.write(6,6,'Cuenta Analitica', style_header_line_blue)
        worksheet.write(6,7,'Debito', style_header_line_blue)
        worksheet.write(6,8,'Credito', style_header_line_blue)
        worksheet.write(6,9,'Saldo Final', style_header_line_blue)
        row = 7
        col = 0
        # General
        list_codes = []
        for lines in report_lines:
            worksheet.write(row,col,' ' * 4 + lines.get('code'))
            worksheet.write(row,col+1,lines.get('name'))
            worksheet.write(row,col+2,lines.get('reference'))
            worksheet.write(row,col+3,lines.get('partner_name'))
            worksheet.write(row,col+4,lines.get('move_name'))
            worksheet.write(row,col+5,lines.get('date'), date_format)
            worksheet.write(row,col+6,lines.get('account_analytic_name'))
            worksheet.write(row,col+7,lines.get('debit'), currency_format)
            worksheet.write(row,col+8,lines.get('credit'), currency_format)
            worksheet.write(row,col+9,lines.get('amount_final'), currency_format)
            row+=1
        fp = io.BytesIO()
        workbook.save(fp)

        export_id = self.env['excel.report.avancys'].create(
            {'excel_file': base64.encodestring(fp.getvalue()), 'file_name': filename})
        res = {
            'view_mode': 'form',
            'res_id': export_id.id,
            'res_model': 'excel.report.avancys',
            'view_type': 'form',
            'type': 'ir.actions.act_window',
            'target': 'new'
        }
        return res
