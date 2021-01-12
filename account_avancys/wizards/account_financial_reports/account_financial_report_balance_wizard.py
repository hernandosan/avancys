# -*- coding: utf-8 -*-
from odoo import api, fields, models
import xlwt
import base64
import io
from odoo.exceptions import UserError
from datetime import datetime


class AccountFinancialReportTrialWizard(models.TransientModel):
	_name = 'account.financial.report.trial.wizard'
	_description = 'Balance de Pruebas'

	company_id = fields.Many2one(
        comodel_name='res.company', 
        string='Compañia', 
        readonly=True,
        default=lambda self: self.env.user.company_id
    )


class AccountFinancialReportBalanceWizard(models.TransientModel):
	_name = 'account.financial.report.balance.wizard'
	_description = 'Balance de Pruebas'

	company_id = fields.Many2one(
        comodel_name='res.company', 
        string='Compañia', 
        readonly=True,
        default=lambda self: self.env.user.company_id
    )
	date_start = fields.Date(
        string='Fecha Inicio',
		default=fields.Date.today(),
    )
	date_end = fields.Date(
        string='Fecha Fin',
		default=fields.Date.today(),
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
	structure_id = fields.Many2one(
        comodel_name='account.financial.structure', 
        string='Estructura'
    )
	levels_ids = fields.Many2many(
        comodel_name='account.financial.levels', 
		relation='balance_wizard_levels_rel',
        string='Niveles', 
        required=True,
        default=lambda self: self.env['account.financial.levels'].search([])
    )
	report_type = fields.Selection(
        string="Tipo de Reporte",
        selection=[
            ('excel', 'Excel'),
            ('pdf', 'PDF'),
        ],
        default='excel',
    )
	
	def _get_lines(self):
		# ACCOUNTS
		accounts = self.env['account.account'].search([])
		# LEVELS
		levels = [x.code for x in self.levels_ids]
		# WHERE
		where_move = ''
		if self.target_move == 'posted':
			where_move += "AND am.state = 'posted'"
		elif self.target_move == 'draft':
			where_move += "AND am.state = 'draft'"

		# INSERT REPORT HEADER
		insert_header_query = (
			"""
			INSERT INTO account_financial_report_balance (company_id, date) VALUES ({company_id}, '{date}') 
			RETURNING ID
			""".format(company_id=self.env.company.id,
					   date=str(datetime.now())[:10])
		)
		self.env.cr.execute(insert_header_query)
		report_id = self.env.cr.fetchone()[0]

		# CALL AND INSERT REPORT LINES
		insert_lines_query = (
			"""
			INSERT INTO 
				account_financial_report_balance_line (
													report_balance_id, 
													bold, 
													account_id, 
													code, 
													name, 
													partner_id, 
													amount_initial, 
													debit, credit, 
													amount_final, 
													level,
													company_id
													)
			SELECT 
				{report_id},
				False,
				moves.account_id,
				aa.code,
				aa.name,
				moves.partner_id,
				moves.amount_initial,
				moves.debit,
				moves.credit,
				moves.amount_final,
				99,
				{company_id}
			FROM (
				SELECT 
				account_id, 
				partner_id, 
				SUM(amount_initial) AS amount_initial, 
				SUM(debit) AS debit, 
				SUM(credit) AS credit, 
				SUM(amount_initial+debit-credit) AS amount_final 
			FROM 
			(
				-- SALDO ENTRE FECHAS SELECCIONADAS
				SELECT 
					aml.account_id, 
					aml.partner_id, 
					0 AS amount_initial, 
					SUM(debit) AS debit, 
					SUM(credit) AS credit 
				FROM 
					account_move_line AS aml 
				INNER JOIN
					account_account AS aa on aa.id = aml.account_id
				INNER JOIN
					account_move as am on am.id = aml.move_id
				WHERE 
					aml.date >= '{date_start}' AND aml.date <= '{date_end}'
				AND
					aml.account_id IN {account_ids}
				{where_move}
				GROUP BY 
					aml.account_id,
					aml.partner_id
				UNION
				-- SALDO INICIAL
				SELECT 
					aml.account_id, 
					aml.partner_id, 
					SUM(aml.debit-aml.credit) AS amount_initial, 
					0 AS debit, 
					0 AS credit 
				FROM 
					account_move_line AS aml
				INNER JOIN
					account_account AS aa on aa.id = aml.account_id 
				INNER JOIN
					account_move as am on am.id = aml.move_id
				WHERE 
					aml.date < '{date_start}'
				{where_move}
				AND
					aml.account_id IN {account_ids}
				GROUP BY 
					aml.account_id,
					aml.partner_id
				) AS 
					lines
				GROUP BY 
					account_id, 
					partner_id
			) AS
				moves
			INNER JOIN
				account_account AS aa ON aa.id = moves.account_id
			ORDER BY
				aa.code ASC
			""".format(account_ids=tuple(accounts.ids),
					   report_id=report_id,
					   company_id=self.env.company.id,
					   date_start=str(self.date_start),
					   date_end=str(self.date_end),
					   where_move=where_move)
		)
		self.env.cr.execute(insert_lines_query)

		# INSERT LINES BY LEVELS
		if '98' in levels:
			query_level_partners = (
				"""
				INSERT INTO 
				account_financial_report_balance_line (
													report_balance_id, 
													bold, 
													account_id, 
													code, 
													name, 
													amount_initial, 
													debit, 
													credit, 
													amount_final, 
													level,
													company_id
													)
				SELECT
					{report_id},
					True,
					account_id,
					code,
					name,
					SUM(amount_initial) AS amount_initial,
					SUM(debit) AS debit,
					SUM(credit) AS credit,
					SUM(amount_final) AS amount_final,
					98,
					{company_id}
				FROM
					account_financial_report_balance_line
				WHERE
					report_balance_id = {report_id}
				GROUP BY
					account_id,
					code,
					name
				""".format(report_id=report_id,
						   company_id=self.env.company.id)
			)
			self.env.cr.execute(query_level_partners)
		
		# ADD STRUCTURE
		for structure in self.structure_id.line_ids.sorted(key=lambda x: x.sequence, reverse=True):
			if str(structure.sequence) in levels:
				query_level = (
					"""
					INSERT INTO 
					account_financial_report_balance_line (
														report_balance_id, 
														bold, 
														account_id, 
														code, 
														name, 
														amount_initial, 
														debit, 
														credit, 
														amount_final, 
														level,
														company_id
														)
					SELECT
						{report_id},
						True,
						aa.id,
						aa.code,
						aa.name,
						SUM(afrtl.amount_initial) AS amount_initial,
						SUM(afrtl.debit) AS debit,
						SUM(afrtl.credit) AS credit,
						SUM(afrtl.amount_final) AS amount_final,
						{sequence},
						{company_id}
					FROM 
						account_financial_report_balance_line AS afrtl
					INNER JOIN
						account_account AS aa ON aa.code = SUBSTRING(afrtl.code FROM 1 FOR {digits})
						AND aa.internal_type = 'view'
						AND LENGTH(afrtl.code) > {digits} 
						AND LENGTH(aa.code) = {digits} 
						AND afrtl.company_id = {company_id}
					WHERE 
						afrtl.level = 99
					AND
						afrtl.report_balance_id = {report_id}
					GROUP BY
						aa.id,
						aa.code,
						aa.name
					""".format(report_id=report_id,
							   company_id=self.env.company.id,
							   digits=structure.digits,
							   sequence=structure.sequence)
				)
				self.env.cr.execute(query_level)
		
		# Zero level
		if '0' in levels:
			query_level_zero = (
				"""
				INSERT INTO 
				account_financial_report_balance_line (
													report_balance_id, 
													bold, 
													account_id, 
													code, 
													name, 
													amount_initial, 
													debit, 
													credit, 
													amount_final, 
													level,
													company_id
													)
				SELECT
					{report_id},
					True,
					null,
					0,
					'{name}',
					SUM(amount_initial) AS amount_initial,
					SUM(debit) AS debit,
					SUM(credit) AS credit,
					SUM(amount_final) AS amount_final,
					0,
					{company_id}
				FROM
					account_financial_report_balance_line
				WHERE
					report_balance_id = {report_id}
				AND
					level = 99
				""".format(report_id=report_id,
						   company_id=self.env.company.id,
						   name=self.structure_id.name)
			)
			self.env.cr.execute(query_level_zero)

		# DELETE INFO 
		if '99' not in levels:
			delete_query = (
				""" 
				DELETE FROM 
					account_financial_report_balance_line 
				WHERE 
					report_balance_id = {report_id} 
				AND 
					company_id = {company_id} 
				AND 
					level = 99 """.format(report_id=report_id,
										  company_id=self.env.company.id)
			)
			self.env.cr.execute(delete_query)
		
		# DELETE EMPTY LINES
		delete_empty_query = (
				""" 
				DELETE FROM 
					account_financial_report_balance_line 
				WHERE 
					amount_initial = 0
				AND 
					debit = 0
				AND 
					credit = 0
				AND
					amount_final = 0	
				"""
		)
		self.env.cr.execute(delete_empty_query)

		# CALL INFO LINES
		select_query_lines = (
			"""
			SELECT 
				report_balance_id, 
				bold, 
				account_id, 
				code, 
				name, 
				partner_id, 
				amount_initial, 
				debit, credit, 
				amount_final, 
				level
			FROM 
				account_financial_report_balance_line
			WHERE 
				report_balance_id = {report_id}
			ORDER BY
				code,
				level,
				bold desc,
				partner_id NULLS FIRST
			""".format(report_id=report_id)
		)
		self.env.cr.execute(select_query_lines)
		results = self.env.cr.dictfetchall()

		lines_res = []
		for result in results:
			res = dict()
			res['code'] = result.get('code')
			res['name'] = result.get('name')
			if not result.get('partner_id') is None:
				res['partner_id'] = self.env['res.partner'].search([('id','=',result.get('partner_id'))]).name
			else:
				res['partner_id'] = ''
			res['debit'] = result.get('debit')
			res['credit'] = result.get('credit')
			res['amount_initial'] = result.get('amount_initial')
			res['amount_final'] = result.get('amount_final')
			res['level'] = result.get('level')
			res['bold'] = result.get('bold')
			lines_res.append(res)

		return lines_res

	def print_report_balance(self):
		if self.date_end or self.date_start:
			if self.date_end <= self.date_start:
				raise UserError('La fecha final no puede ser inferior a la de inicio.')
		lines_res = self._get_lines()
		return self._print_report_balance_excel(lines_res)
    
	def _print_report_balance_excel(self,report_lines):
		company_id = self.env.company
		user = self.env.user
		date = datetime.now()
		filename = 'BALANCE_DE_PRUEBAS' + '_' + company_id.name + '_' + user.name + '_' + str(date)[:10] + '.xls'
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
			"font:bold on,color blue;")
		style_line.font.colour_index = xlwt.Style.colour_map['blue_2']
		style_line.num_format_str = '$#,##0.00'
		style_line_2 = xlwt.easyxf("align: horiz right;")
		currency_format = xlwt.XFStyle()
		currency_format.num_format_str = '$#,##0.00'
		worksheet.row(0).height_mismatch = True
		worksheet.row(0).height = 500
		# HEADER
		worksheet.write_merge(0, 0, 0, 5, self.env['res.users'].browse(self.env.uid).company_id.name + " : Balance de Pruebas", style=style_header)
		worksheet.write(2,0,'Desde:', style_header_line)
		worksheet.write(2,1,self.date_start,date_format)
		worksheet.write(2,2,'Hasta:', style_header_line)
		worksheet.write(2,3,self.date_end,date_format)
		worksheet.write(3,0,'Estado:', style_header_line)
		worksheet.write(4,0,'Fecha de Impresión:', style_header_line)
		worksheet.write(4,1,str(datetime.now()))
		# EXCEL FIELDS
		worksheet.write(6,0,'Codigo', style_header_line_blue)
		worksheet.write(6,1,'Cuenta', style_header_line_blue)
		worksheet.write(6,2,'Tercero', style_header_line_blue)
		worksheet.write(6,3,'Saldo Inicial', style_header_line_blue)
		worksheet.write(6,4,'Debito', style_header_line_blue)
		worksheet.write(6,5,'Credito', style_header_line_blue)
		worksheet.write(6,6,'Saldo Final', style_header_line_blue)
		row = 7
		col = 0
		# General
		list_codes = []
		for lines in report_lines:
			if lines['bold'] == True:
				worksheet.write(row,col,lines.get('code'), style_line)
				worksheet.write(row,col+1,lines.get('name'), style_line)
				worksheet.write(row,col+2,lines.get('partner_id'), style_line)
				worksheet.write(row,col+3,lines.get('amount_initial'), style_line)
				worksheet.write(row,col+4,lines.get('debit'), style_line)
				worksheet.write(row,col+5,lines.get('credit'), style_line)
				worksheet.write(row,col+6,lines.get('amount_final'), style_line)
				row+=1
				continue
			worksheet.write(row,col,' ' * 4 + lines.get('code'))
			worksheet.write(row,col+1,lines.get('name'))
			worksheet.write(row,col+2,lines.get('partner_id'))
			worksheet.write(row,col+3,lines.get('amount_initial'), currency_format)
			worksheet.write(row,col+4,lines.get('debit'), currency_format)
			worksheet.write(row,col+5,lines.get('credit'), currency_format)
			worksheet.write(row,col+6,lines.get('amount_final'), currency_format)
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
