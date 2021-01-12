# -*- coding: utf-8 -*-
from odoo import api, fields, models
import xlwt
import base64
import io
from odoo.exceptions import UserError
from datetime import datetime
import time


class AccountFinancialReportAssistantWizard(models.TransientModel):
    _name = 'account.financial.report.assistant.wizard'
    _description = 'Libro Auxiliar'

    company_id = fields.Many2one(
        comodel_name='res.company', 
        string='Compañia', 
        readonly=True,
        default=lambda self: self.env.user.company_id
    )
    journal_ids = fields.Many2many(
        comodel_name='account.journal', 
        string='Diarios', 
        required=True,
        default=lambda self: self.env['account.journal'].search([])
    )
    date_from = fields.Date(
        string='Fecha Inicio'
    )
    date_to = fields.Date(
        string='Fecha Fin'
    )
    target_move = fields.Selection(
        selection=[
            ('posted', 'Movimientos Asentados'),
            ('all', 'Todos los movimientos'),
        ], 
        string='Movimientos', 
        required=True, 
        default='posted'
    )
    display_account = fields.Selection(
        selection=[
            ('all', 'Todas'), 
            ('movement', 'Con movimientos'),
            ('not_zero', 'Con saldo diferente de cero'), 
        ],
        string='Cuentas', 
        required=True, 
        default='movement'
    )
    report_type = fields.Selection(
        string="Tipo de Reporte",
        selection=[
            ('excel', 'Excel'),
            ('pdf', 'PDF'),
        ],
        default='excel',
    )
    sortby = fields.Selection(
        selection=[
            ('sort_date', 'Fecha'), 
            ('sort_journal_partner', 'Diario y Tercero')
        ], 
        string='Ordenado Por',
        required=True, 
        default='sort_date'
    )
    initial_balance = fields.Boolean(
        string='Incluir saldo inicial',
        help='Si selecciono la opción fecha, se agregará una fila que mostrará el saldo inicial dependiendo del filtro escogido.'
    )

    def _get_account_move_entry(self, accounts, init_balance, sortby, display_account):
        """
        :param:
                accounts: the recordset of accounts
                init_balance: boolean value of initial_balance
                sortby: sorting by date or partner and journal
                display_account: type of account(receivable, payable and both)

        Returns a dictionary of accounts with following key and value {
                'code': account code,
                'name': account name,
                'debit': sum of total debit amount,
                'credit': sum of total credit amount,
                'balance': total balance,
                'amount_currency': sum of amount_currency,
                'move_lines': list of move line
        }
        """
        cr = self.env.cr
        MoveLine = self.env['account.move.line']
        move_lines = {x: [] for x in accounts.ids}

        # Prepare initial sql query and Get the initial move lines
        if init_balance:
            init_tables, init_where_clause, init_where_params = MoveLine.with_context(date_from=self.env.context.get('date_from'), date_to=False, initial_bal=True)._query_get()
            init_wheres = [""]
            if init_where_clause.strip():
                init_wheres.append(init_where_clause.strip())
            init_filters = " AND ".join(init_wheres)
            filters = init_filters.replace('account_move_line__move_id', 'm').replace('account_move_line', 'l')
            sql = ("""SELECT 0 AS lid, l.account_id AS account_id, '' AS ldate, '' AS lcode, 0.0 AS amount_currency, '' AS lref, 'Initial Balance' AS lname, COALESCE(SUM(l.debit),0.0) AS debit, COALESCE(SUM(l.credit),0.0) AS credit, COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit), 0) as balance, '' AS lpartner_id,\
                '' AS move_name, '' AS mmove_id, '' AS currency_code,\
                NULL AS currency_id,\
                '' AS invoice_id, '' AS invoice_type, '' AS invoice_number,\
                '' AS partner_name\
                FROM account_move_line l\
                LEFT JOIN account_move m ON (l.move_id=m.id)\
                LEFT JOIN res_currency c ON (l.currency_id=c.id)\
                LEFT JOIN res_partner p ON (l.partner_id=p.id)\
                JOIN account_journal j ON (l.journal_id=j.id)\
                WHERE l.account_id IN %s""" + filters + ' GROUP BY l.account_id')
            params = (tuple(accounts.ids),) + tuple(init_where_params)
            cr.execute(sql, params)
            for row in cr.dictfetchall():
                move_lines[row.pop('account_id')].append(row)

        sql_sort = 'l.date, l.move_id'
        if sortby == 'sort_journal_partner':
            sql_sort = 'j.code, p.name, l.move_id'

        # Prepare sql query base on selected parameters from wizard
        tables, where_clause, where_params = MoveLine._query_get()
        wheres = [""]
        if where_clause.strip():
            wheres.append(where_clause.strip())
        filters = " AND ".join(wheres)
        filters = filters.replace('account_move_line__move_id', 'm').replace('account_move_line', 'l')

        # Get move lines base on sql query and Calculate the total balance of move lines
        sql = ('''SELECT l.id AS lid, l.account_id AS account_id, l.date AS ldate, j.code AS lcode, l.currency_id, l.amount_currency, l.ref AS lref, l.name AS lname, COALESCE(l.debit,0) AS debit, COALESCE(l.credit,0) AS credit, COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit), 0) AS balance,\
            m.name AS move_name, c.symbol AS currency_code, p.name AS partner_name\
            FROM account_move_line l\
            JOIN account_move m ON (l.move_id=m.id)\
            LEFT JOIN res_currency c ON (l.currency_id=c.id)\
            LEFT JOIN res_partner p ON (l.partner_id=p.id)\
            JOIN account_journal j ON (l.journal_id=j.id)\
            JOIN account_account acc ON (l.account_id = acc.id) \
            WHERE l.account_id IN %s ''' + filters + ''' GROUP BY l.id, l.account_id, l.date, j.code, l.currency_id, l.amount_currency, l.ref, l.name, m.name, c.symbol, p.name ORDER BY ''' + sql_sort)
        params = (tuple(accounts.ids),) + tuple(where_params)
        cr.execute(sql, params)

        for row in cr.dictfetchall():
            balance = 0
            for line in move_lines.get(row['account_id']):
                balance += line['debit'] - line['credit']
            row['balance'] += balance
            move_lines[row.pop('account_id')].append(row)

        # Calculate the debit, credit and balance for Accounts
        account_res = []
        for account in accounts:
            currency = account.currency_id and account.currency_id or account.company_id.currency_id
            res = dict((fn, 0.0) for fn in ['credit', 'debit', 'balance'])
            res['code'] = account.code
            res['name'] = account.name
            res['move_lines'] = move_lines[account.id]
            for line in res.get('move_lines'):
                res['debit'] += line['debit']
                res['credit'] += line['credit']
                res['balance'] = line['balance']
            if display_account == 'all':
                account_res.append(res)
            if display_account == 'movement' and res.get('move_lines'):
                account_res.append(res)
            if display_account == 'not_zero' and not currency.is_zero(res['balance']):
                account_res.append(res)

        return account_res

    def _print_general_ledger_excel_report(self,report_lines):
        company_id = self.env.company
        user = self.env.user
        date = datetime.now()
        filename = 'LIBRO_AUXILIAR' + '_' + company_id.name + '_' + user.name + '_' + str(date)[:10] + '.xls'
        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet('Hoja 1')
        date_format = xlwt.XFStyle()
        currency_format = xlwt.XFStyle()
        date_format.num_format_str = 'dd/mm/yyyy'
        currency_format.num_format_str = '$#,##0.00'
        style_header = xlwt.easyxf(
            "font:height 300; font: name Liberation Sans, bold on,color black; align: horiz center")
        style_line = xlwt.easyxf(
            "font:bold on,color black;")
        style_line.num_format_str = '$#,##0.00'
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
        style_line.font.colour_index = xlwt.Style.colour_map['blue_2']
        worksheet.row(0).height_mismatch = True
        worksheet.row(0).height = 500
        # HEADER
        worksheet.write_merge(0, 0, 0, 5, company_id.name + " : Libro Auxiliar", style=style_header)
        worksheet.write(2,0,'Desde:', style_header_line)
        worksheet.write(2,1,self.date_from or '',date_format)
        worksheet.write(2,2,'Hasta:', style_header_line)
        worksheet.write(2,3,self.date_to or '',date_format)
        worksheet.write(3,0,'Estado:', style_header_line)
        worksheet.write(4,0,'Fecha de Impresión:', style_header_line)
        worksheet.write(4,1,str(datetime.now()))
        # EXCEL FIELDS
        worksheet.write(6, 0, 'Fecha', style_header_line_blue)
        worksheet.write(6, 1, 'Diario',style_header_line_blue)
        worksheet.write(6, 2, 'Tercero', style_header_line_blue)
        worksheet.write(6, 3, 'Referencia',style_header_line_blue)
        worksheet.write(6, 4, 'Asiento', style_header_line_blue)
        worksheet.write(6, 5, 'Linea', style_header_line_blue)
        worksheet.write(6, 6, 'Debito', style_header_line_blue)
        worksheet.write(6, 7, 'Credito', style_header_line_blue)
        worksheet.write(6, 8, 'Saldo', style_header_line_blue)
        row = 7
        col = 0

        for line in report_lines:
            flag = False
            worksheet.write_merge(row,row, 0,5, line.get('code') + ' ' + line.get('name'),style=style_line )
            worksheet.write(row, col+6, line.get('debit'),style=style_line)
            worksheet.write(row, col+7, line.get('credit'),style=style_line)
            worksheet.write(row, col+8, line.get('balance'),style=style_line)
            for move_line in line.get('move_lines'):
                row+=1
                worksheet.write(row, col, move_line.get('ldate'),date_format)
                worksheet.write(row, col + 1, move_line.get('lcode'))
                worksheet.write(row, col + 2, move_line.get('partner_name'))
                worksheet.write(row, col + 3, move_line.get('lref'))
                worksheet.write(row, col + 4, move_line.get('move_name'))
                worksheet.write(row, col + 5, move_line.get('lname'))
                worksheet.write(row, col + 6, move_line.get('debit'),currency_format)
                worksheet.write(row, col + 7, move_line.get('credit'),currency_format)
                worksheet.write(row, col + 8, move_line.get('balance'),currency_format)
                flag = True
            row += 1
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

    def print_report_assistant(self):
        if self.date_to or self.date_from:
            if self.date_to <= self.date_from:
                raise UserError('End date should be greater then to start date.')
        init_balance = self.initial_balance
        sortby = self.sortby
        display_account = self.display_account
        codes = []
        if self.journal_ids:
            codes = [journal.code for journal in
                        self.env['account.journal'].search([('id', 'in', self.journal_ids.ids)])]
        used_context_dict = {
            'state': self.target_move,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'journal_ids': [a.id for a in self.journal_ids],
            'strict_range': True
        }
        accounts = self.env['account.account'].search([])
        accounts_res = self.with_context(used_context_dict)._get_account_move_entry(accounts, init_balance, sortby,
                                                                                    display_account)
        final_dict = {}
        final_dict.update(
            {
                'time': time,
                'Account': accounts_res,
                'print_journal': codes,
                'display_account': display_account,
                'target_move': self.target_move,
                'sortby': sortby,
                'date_from': self.date_from,
                'date_to': self.date_to
            }
        )
        return self._print_general_ledger_excel_report(accounts_res)