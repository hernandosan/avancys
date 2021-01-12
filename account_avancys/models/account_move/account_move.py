# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    tax_line_ids = fields.One2many('account.move.tax', 'move_id', string='Impuestos')
    manual_tax = fields.Boolean(string='Ingresar Manualmente los impuestos', help='Esta opción permite agregar y quitar impuestos de manera manual, desactivando de esta manera la actualización automática')
        
    def subtotal_per_tax(self, lines, tax):
        subtotal = 0
        new_lines = []
        for line in lines:
            if tax.id in line.tax_ids.ids:
                new_lines.append(line)
        if new_lines:
            subtotal += sum([x.price_subtotal for x in new_lines])
        return subtotal

    def subtotal_per_tax2(self, lines, tax, city_id, ciiu):
        subtotal = 0
        new_lines = []
        key = "{tax}-{city}-{ciiu}".format(tax=tax, city=city_id, ciiu=ciiu)
        for line in lines:
            if tax.id in line.tax_ids.ids:
                if city_id == line.city_id and ciiu == line.ciiu_id:
                    new_lines.append(line)
        if new_lines:
            subtotal += sum([x.price_subtotal for x in new_lines])
        return subtotal

    def button_reset_taxes(self):
        fposition_obj =  self.env['account.fiscal.position']
        # Ciiu ICA
        ciiu_ica = (bool)(self.env['ir.config_parameter'].sudo().get_param('account_avancys.ciiu_ica'))
        city_cc = (bool)(self.env['ir.config_parameter'].sudo().get_param('account_avancys.city_cc'))

        # Odoo v8
        tax_subtotals = {}
        tax_keys_subtotals = {}
        company_partner = False
        cr = self._cr
        
        for record in self:
            if record.manual_tax:
                continue
            if ciiu_ica:
                company_partner = record.partner_id
            
            if record.move_type in ('out_invoice', 'out_refund'):
                company_partner = record.company_id.partner_id

            if record.is_sale_document(include_receipts=True) or record.is_purchase_document(include_receipts=True):
                for line in record.invoice_line_ids:

                    if ciiu_ica:
                        result_taxes = []
                        taxes_to_map = {}
                        city_id = False

                        for tax_id in line.tax_ids:
                            fposition = record.fiscal_position_id or record.partner_id.property_account_position_id or False
                            
                            if not line.ciiu_id:
                                if record.is_sale_document(include_receipts=True):
                                    line.ciiu_id = record.company_id.partner_id.ciiu_id.id
                                elif record.is_purchase_document(include_receipts=True):
                                    line.ciiu_id = record.partner_id.ciiu_id.id

                            if not line.city_id:
                                if record.is_sale_document(include_receipts=True):
                                    line.city_id = record.company_id.partner_id.city_id
                                elif record.is_purchase_document(include_receipts=True):
                                    line.city_id = record.partner_shipping_id.city_id
                            
                            if tax_id.check_lines and city_cc:
                                city_id = line.analytic_account_id.city_id
                            elif tax_id.check_lines:
                                city_id = line.city_id
                                    
                            ciiu = line.ciiu_id

                            if tax_id.child_cities_ids:
                                tax_key = "{tax}-{city}-{ciiu}".format(tax=tax_id.id, city=city_id, ciiu=ciiu)
                                if tax_key not in tax_keys_subtotals:
                                    tax_keys_subtotals[tax_key] = self.subtotal_per_tax2(record.invoice_line_ids, tax_id, city_id, line.ciiu_id)
                                ind_taxtomap = {tax_id: self.subtotal_per_tax2(record.invoice_line_ids, tax_id, city, line.ciiu_id)}
                                restax = fposition_obj.map_tax2(fposition, ind_taxtomap, company_partner, city, ciiu, record)
                                if restax:
                                    result_taxes.append(restax[0])
                                taxes_to_map[tax_id] = self.subtotal_per_tax2(record.invoice_line_ids, tax_id, city_id, line.ciiu_id)
                            else:
                                if tax_id.id not in tax_subtotals:
                                    tax_subtotals[tax_id.id] = self.subtotal_per_tax(record.invoice_line_ids, tax_id)
                                ind_taxtomap = {tax_id: tax_subtotals[tax_id.id]}

                                restax = fposition_obj.map_tax2(fposition, ind_taxtomap, company_partner, city_id, ciiu, record)
                                if restax:
                                    result_taxes.append(restax[0])
                                taxes_to_map[tax_id] = tax_subtotals[tax_id.id]
                    else:
                        # Politica General
                        taxes_to_map = {}
                        city_id = False

                        for tax_id in line.tax_ids:
                            if tax_id.id not in tax_subtotals:
                                tax_subtotals[tax_id.id] = self.subtotal_per_tax(record.invoice_line_ids, tax_id)
                            taxes_to_map[tax_id] = tax_subtotals[tax_id.id]
                        result_taxes = [x for x in line.tax_ids.ids]
                        fposition = record.fiscal_position_id or record.partner_id.property_account_position_id or False

                        if result_taxes:
                            reteica_ck_lines = """
                                SELECT 
                                    id, 
                                    check_lines 
                                FROM 
                                    account_tax 
                                WHERE 
                                    check_lines = 'true' 
                                and 
                                    id in (%s)
                            """ % ','.join(str(x) for x in result_taxes)
                            cr.execute(reteica_ck_lines)
                            reteica_ck_lines = cr.dictfetchall()

                            if reteica_ck_lines and reteica_ck_lines[0]['check_lines'] is True:
                                if city_cc:
                                    city_id = line.analytic_account_id.city_id
                                else:
                                    city_id = line.city_id
                            else:
                                if record.partner_shipping_id and record.partner_shipping_id.city_id:
                                    city_id = record.partner_shipping_id.city_id
                                elif company_partner and company_partner.city_id:
                                    city_id = company_partner.city_id

                            result_taxes = fposition_obj.map_tax2(fposition, taxes_to_map, company_partner, city_id, line.ciiu_id, record)
                    line.write({
                        'tax_ids': [(6, 0, result_taxes)]
                    })
            # Actualizar Valores
            for line in record.invoice_line_ids:
                line._onchange_mark_recompute_taxes()
                if not line.tax_repartition_line_id:
                    line.recompute_tax_line = True
            record._onchange_invoice_line_ids()    

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------          

    @api.onchange('invoice_line_ids')
    def _onchange_invoice_line_ids(self):
        res = super()._onchange_invoice_line_ids()
        for record in self:
            if not record.manual_tax:
                record._get_taxes_invoice()
                record._onchange_invoice_line_ids_2()
        return res
    
    def _onchange_invoice_line_ids_2(self):
        current_invoice_lines = self.line_ids.filtered(lambda line: not line.exclude_from_invoice_tab)
        others_lines = self.line_ids - current_invoice_lines
        if others_lines and current_invoice_lines - self.invoice_line_ids:
            others_lines[0].recompute_tax_line = True
        self.line_ids = others_lines + self.invoice_line_ids
        self._onchange_recompute_dynamic_lines()
        self._onchange_tax_lines()

    def _recompute_payment_terms_lines(self):
        ''' Compute the dynamic payment term lines of the journal entry.'''
        self.ensure_one()
        self = self.with_company(self.company_id)
        in_draft_mode = self != self._origin
        today = fields.Date.context_today(self)
        self = self.with_company(self.journal_id.company_id)

        def _get_payment_terms_computation_date(self):
            ''' Get the date from invoice that will be used to compute the payment terms.
            :param self:    The current account.move record.
            :return:        A datetime.date object.
            '''
            if self.invoice_payment_term_id:
                return self.invoice_date or today
            else:
                return self.invoice_date_due or self.invoice_date or today

        def _get_payment_terms_account(self, payment_terms_lines):
            ''' Get the account from invoice that will be set as receivable / payable account.
            :param self:                    The current account.move record.
            :param payment_terms_lines:     The current payment terms lines.
            :return:                        An account.account record.
            '''
            if payment_terms_lines:
                # Retrieve account from previous payment terms lines in order to allow the user to set a custom one.
                return payment_terms_lines[0].account_id
            elif self.partner_id:
                # Retrieve account from partner.
                if self.is_sale_document(include_receipts=True):
                    return self.partner_id.property_account_receivable_id
                else:
                    return self.partner_id.property_account_payable_id
            else:
                # Search new account.
                domain = [
                    ('company_id', '=', self.company_id.id),
                    ('internal_type', '=', 'receivable' if self.move_type in ('out_invoice', 'out_refund', 'out_receipt') else 'payable'),
                ]
                return self.env['account.account'].search(domain, limit=1)

        def _compute_payment_terms(self, date, total_balance, total_amount_currency):
            ''' Compute the payment terms.
            :param self:                    The current account.move record.
            :param date:                    The date computed by '_get_payment_terms_computation_date'.
            :param total_balance:           The invoice's total in company's currency.
            :param total_amount_currency:   The invoice's total in invoice's currency.
            :return:                        A list <to_pay_company_currency, to_pay_invoice_currency, due_date>.
            '''
            if self.invoice_payment_term_id:
                to_compute = self.invoice_payment_term_id.compute(total_balance, date_ref=date, currency=self.company_id.currency_id)
                if self.currency_id == self.company_id.currency_id:
                    # Single-currency.
                    return [(b[0], b[1], b[1]) for b in to_compute]
                else:
                    # Multi-currencies.
                    to_compute_currency = self.invoice_payment_term_id.compute(total_amount_currency, date_ref=date, currency=self.currency_id)
                    return [(b[0], b[1], ac[1]) for b, ac in zip(to_compute, to_compute_currency)]
            else:
                return [(fields.Date.to_string(date), total_balance, total_amount_currency)]

        def _compute_diff_payment_terms_lines(self, existing_terms_lines, account, to_compute):
            ''' Process the result of the '_compute_payment_terms' method and creates/updates corresponding invoice lines.
            :param self:                    The current account.move record.
            :param existing_terms_lines:    The current payment terms lines.
            :param account:                 The account.account record returned by '_get_payment_terms_account'.
            :param to_compute:              The list returned by '_compute_payment_terms'.
            '''
            # As we try to update existing lines, sort them by due date.
            existing_terms_lines = existing_terms_lines.sorted(lambda line: line.date_maturity or today)
            existing_terms_lines_index = 0

            # Recompute amls: update existing line or create new one for each payment term.
            new_terms_lines = self.env['account.move.line']
            for date_maturity, balance, amount_currency in to_compute:
                if self.journal_id.company_id.currency_id.is_zero(balance) and len(to_compute) > 1:
                    continue

                if existing_terms_lines_index < len(existing_terms_lines):
                    # Update existing line.
                    candidate = existing_terms_lines[existing_terms_lines_index]
                    existing_terms_lines_index += 1
                    if candidate._origin:
                        candidate.write({
                            'date_maturity': date_maturity,
                            'amount_currency': -amount_currency,
                            'debit': balance < 0.0 and -balance or 0.0,
                            'credit': balance > 0.0 and balance or 0.0,
                        })
                    else:
                        candidate.update({
                            'date_maturity': date_maturity,
                            'amount_currency': -amount_currency,
                            'debit': balance < 0.0 and -balance or 0.0,
                            'credit': balance > 0.0 and balance or 0.0,
                        })
                else:
                    # Create new line.
                    create_method = in_draft_mode and self.env['account.move.line'].new or self.env['account.move.line'].create
                    candidate = create_method({
                        'name': self.payment_reference or '',
                        'debit': balance < 0.0 and -balance or 0.0,
                        'credit': balance > 0.0 and balance or 0.0,
                        'quantity': 1.0,
                        'amount_currency': -amount_currency,
                        'date_maturity': date_maturity,
                        'move_id': self.id,
                        'currency_id': self.currency_id.id,
                        'account_id': account.id,
                        'partner_id': self.commercial_partner_id.id,
                        'exclude_from_invoice_tab': True,
                    })
                new_terms_lines += candidate
                if in_draft_mode:
                    candidate.update(candidate._get_fields_onchange_balance(force_computation=True))
            return new_terms_lines

        existing_terms_lines = self.line_ids.filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
        others_lines = self.line_ids.filtered(lambda line: line.account_id.user_type_id.type not in ('receivable', 'payable'))
        company_currency_id = (self.company_id or self.env.company).currency_id
        total_balance = sum(others_lines.mapped(lambda l: company_currency_id.round(l.balance)))
        total_amount_currency = sum(others_lines.mapped('amount_currency'))

        if not others_lines:
            self.line_ids -= existing_terms_lines
            return

        computation_date = _get_payment_terms_computation_date(self)
        account = _get_payment_terms_account(self, existing_terms_lines)
        to_compute = _compute_payment_terms(self, computation_date, total_balance, total_amount_currency)
        new_terms_lines = _compute_diff_payment_terms_lines(self, existing_terms_lines, account, to_compute)

        # Remove old terms lines that are no longer needed.
        self.line_ids -= existing_terms_lines - new_terms_lines

        if new_terms_lines:
            self.payment_reference = new_terms_lines[-1].name or ''
            self.invoice_date_due = new_terms_lines[-1].date_maturity
    
    # TAX ONCHANGE
    def _onchange_subtotal_per_tax(self, lines, tax):
        subtotal = 0
        new_lines = []
        for line in lines:
            tax_ids = line.tax_ids.ids
            default_tax_ids = line._get_computed_taxes().ids
            for default_tax in default_tax_ids:
                if default_tax not in tax_ids:
                    tax_ids.append(default_tax)
            if tax.id in tax_ids:
                new_lines.append(line)
        if new_lines:
            subtotal += sum([x.price_subtotal for x in new_lines])
        return subtotal

    def _onchange_subtotal_per_tax2(self, lines, tax, city_id, ciiu):
        subtotal = 0
        new_lines = []
        key = "{tax}-{city}-{ciiu}".format(tax=tax, city=city_id, ciiu=ciiu)
        for line in lines:
            tax_ids = line.tax_ids.ids
            default_tax_ids = line._get_computed_taxes().ids
            for default_tax in default_tax_ids:
                if default_tax not in tax_ids:
                    tax_ids.append(default_tax)
            if tax.id in tax_ids:
                if city_id == line.city_id and ciiu == line.ciiu_id:
                    new_lines.append(line)
        if new_lines:
            subtotal += sum([x.price_subtotal for x in new_lines])
        return subtotal

    def _get_taxes_invoice(self):
        fposition_obj =  self.env['account.fiscal.position']
        # Ciiu ICA
        ciiu_ica = (bool)(self.env['ir.config_parameter'].sudo().get_param('account_avancys.ciiu_ica'))
        city_cc = (bool)(self.env['ir.config_parameter'].sudo().get_param('account_avancys.city_cc'))

        # Odoo v8
        tax_subtotals = {}
        tax_keys_subtotals = {}
        company_partner = False
        cr = self._cr
        
        for record in self:
            if ciiu_ica:
                company_partner = record.partner_id
            
            if record.move_type in ('out_invoice', 'out_refund'):
                company_partner = record.company_id.partner_id

            if record.is_sale_document(include_receipts=True) or record.is_purchase_document(include_receipts=True):
                for line in record.invoice_line_ids:

                    if ciiu_ica:
                        result_taxes = []
                        taxes_to_map = {}
                        city_id = False

                        # Taxes by default in onchange
                        tax_ids = line.tax_ids.ids
                        default_tax_ids = line._get_computed_taxes().ids
                        for default_tax in default_tax_ids:
                            if default_tax not in tax_ids:
                                tax_ids.append(default_tax)

                        for tax in tax_ids:
                            tax_id = self.env['account.tax'].search([('id','=',tax)])
                            tax_id = tax_id._origin
                            fposition = record.fiscal_position_id or record.partner_id.property_account_position_id or False
                            
                            if not line.ciiu_id:
                                if record.is_sale_document(include_receipts=True):
                                    line.ciiu_id = record.company_id.partner_id.ciiu_id.id
                                elif record.is_purchase_document(include_receipts=True):
                                    line.ciiu_id = record.partner_id.ciiu_id.id

                            if not line.city_id:
                                if record.is_sale_document(include_receipts=True):
                                    line.city_id = record.company_id.partner_id.city_id
                                elif record.is_purchase_document(include_receipts=True):
                                    line.city_id = record.partner_shipping_id.city_id
                                    
                            ciiu = line.ciiu_id

                            if tax_id.check_lines and city_cc:
                                city_id = line.analytic_account_id.city_id
                            elif tax_id.check_lines:
                                city_id = line.city_id

                            if tax_id.child_cities_ids:
                                tax_key = "{tax}-{city}-{ciiu}".format(tax=tax_id.id, city=city_id, ciiu=ciiu)
                                if tax_key not in tax_keys_subtotals:
                                    tax_keys_subtotals[tax_key] = self._onchange_subtotal_per_tax2(record.invoice_line_ids, tax_id, city_id, line.ciiu_id)
                                ind_taxtomap = {tax_id: self._onchange_subtotal_per_tax2(record.invoice_line_ids, tax_id, city_id, line.ciiu_id)}
                                restax = fposition_obj.map_tax2(fposition, ind_taxtomap, company_partner, city_id, ciiu, record)
                                if restax:
                                    result_taxes.append(restax[0])
                                taxes_to_map[tax_id] = self._onchange_subtotal_per_tax2(record.invoice_line_ids, tax_id, city_id, line.ciiu_id)
                            else:
                                if tax_id.id not in tax_subtotals:
                                    tax_subtotals[tax_id.id] = self._onchange_subtotal_per_tax(record.invoice_line_ids, tax_id)
                                ind_taxtomap = {tax_id: tax_subtotals[tax_id.id]}

                                restax = fposition_obj.map_tax2(fposition, ind_taxtomap, company_partner, city_id, ciiu, record)
                                if restax:
                                    result_taxes.append(restax[0])
                                taxes_to_map[tax_id] = tax_subtotals[tax_id.id]
                    else:
                        # Politica General
                        taxes_to_map = {}
                        city_id = False

                        # Taxes by default in onchange
                        tax_ids = line.tax_ids.ids
                        default_tax_ids = line._get_computed_taxes().ids
                        for default_tax in default_tax_ids:
                            if default_tax not in tax_ids:
                                tax_ids.append(default_tax)

                        for tax in tax_ids:
                            tax_id = self.env['account.tax'].search([('id','=',tax)])
                            if tax_id.id not in tax_subtotals:
                                tax_subtotals[tax_id.id] = self._onchange_subtotal_per_tax(record.invoice_line_ids, tax_id)
                            taxes_to_map[tax_id] = tax_subtotals[tax_id.id]
                        result_taxes = [x for x in line.tax_ids.ids]
                        fposition = record.fiscal_position_id or record.partner_id.property_account_position_id or False

                        if result_taxes:
                            reteica_ck_lines = """
                                SELECT 
                                    id, 
                                    check_lines 
                                FROM 
                                    account_tax 
                                WHERE 
                                    check_lines = 'true' 
                                and 
                                    id in (%s)
                            """ % ','.join(str(x) for x in result_taxes)
                            cr.execute(reteica_ck_lines)
                            reteica_ck_lines = cr.dictfetchall()

                            if reteica_ck_lines and reteica_ck_lines[0]['check_lines'] is True:
                                if city_cc:
                                    city_id = line.analytic_account_id.city_id
                                else:
                                    city_id = line.city_id
                            else:
                                if record.partner_shipping_id and record.partner_shipping_id.city_id:
                                    city_id = record.partner_shipping_id.city_id
                                elif company_partner and company_partner.city_id:
                                    city_id = company_partner.city_id

                            result_taxes = fposition_obj.map_tax2(fposition, taxes_to_map, company_partner, city_id, line.ciiu_id, record)
                    if line._origin:
                        line.write({
                            'tax_ids': [(6, 0, result_taxes)]
                        })
                    else:
                        line.update({
                            'tax_ids': [(6, 0, result_taxes)]
                        })
            # Actualizar Valores
            for line in record.invoice_line_ids:
                line._onchange_mark_recompute_taxes()
                if not line.tax_repartition_line_id:
                    line.recompute_tax_line = True
    
    def _onchange_tax_lines(self):
        for record in self:
            # Add Tax Lines
            for line in record.line_ids.filtered(lambda x: x.tax_line_id.id != False):
                if line.tax_line_id.id not in [x.tax_id.id for x in record.tax_line_ids]:
                    vals = {
                        'account_id': line.account_id.id,
                        'tax_id': line.tax_line_id.id,
                        'name': line.name,
                        'credit': line.credit,
                        'debit': line.debit,
                        'tax_base_amount': line.tax_base_amount,
                    }
                    new_line = self.env['account.move.tax'].create(vals)
                    record.tax_line_ids += new_line
                else:
                    for line_tax in record.tax_line_ids.filtered(lambda x: x.tax_id.id == line.tax_line_id.id):
                        line_tax.update({
                            'credit': line.credit,
                            'debit': line.debit,
                            'tax_base_amount': line.tax_base_amount,
                        })
            # Remove Tax Lines
            for tax_line in record.tax_line_ids:
                if tax_line.tax_id.id not in [x.tax_line_id.id for x in record.line_ids.filtered(lambda x: x.tax_line_id.id != False)]:
                    record.tax_line_ids -= tax_line
                
    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------
    
    def action_post(self):
        for record in self:
            if record.is_sale_document(include_receipts=True) or record.is_purchase_document(include_receipts=True):
                if not record.manual_tax:
                    record.button_reset_taxes()
        res = super().action_post()
        for record in self:
            record._check_balanced_post()
        return res
    
    @api.model
    def get_return_types(self):
        return ['out_refund', 'in_refund']
    
    def is_return_document(self):
        return self.move_type in self.get_return_types()
    
    def _check_balanced(self):
        ''' Assert the move is fully balanced debit = credit.
        An error is raised if it's not the case.
        '''
        moves = self.filtered(lambda move: move.line_ids)
        if not moves:
            return

        # /!\ As this method is called in create / write, we can't make the assumption the computed stored fields
        # are already done. Then, this query MUST NOT depend of computed stored fields (e.g. balance).
        # It happens as the ORM makes the create with the 'no_recompute' statement.
        self.env['account.move.line'].flush(self.env['account.move.line']._fields)
        self.env['account.move'].flush(['journal_id'])
        self._cr.execute('''
            SELECT line.move_id, ROUND(SUM(line.debit - line.credit), currency.decimal_places)
            FROM account_move_line line
            JOIN account_move move ON move.id = line.move_id
            JOIN account_journal journal ON journal.id = move.journal_id
            JOIN res_company company ON company.id = journal.company_id
            JOIN res_currency currency ON currency.id = company.currency_id
            WHERE line.move_id IN %s
            GROUP BY line.move_id, currency.decimal_places
            HAVING ROUND(SUM(line.debit - line.credit), currency.decimal_places) != 0.0;
        ''', [tuple(self.ids)])

        query_res = self._cr.fetchall()
        if query_res:
            ids = [res[0] for res in query_res]
            sums = [res[1] for res in query_res]
            if self.state != 'draft':
                raise UserError(_("Cannot create unbalanced journal entry. Ids: %s\nDifferences debit - credit: %s") % (ids, sums))
    
    def _check_balanced_post(self):
        ''' Assert the move is fully balanced debit = credit.
        An error is raised if it's not the case.
        '''
        moves = self.filtered(lambda move: move.line_ids)
        if not moves:
            return

        # /!\ As this method is called in create / write, we can't make the assumption the computed stored fields
        # are already done. Then, this query MUST NOT depend of computed stored fields (e.g. balance).
        # It happens as the ORM makes the create with the 'no_recompute' statement.
        self.env['account.move.line'].flush(self.env['account.move.line']._fields)
        self.env['account.move'].flush(['journal_id'])
        self._cr.execute('''
            SELECT line.move_id, ROUND(SUM(line.debit - line.credit), currency.decimal_places)
            FROM account_move_line line
            JOIN account_move move ON move.id = line.move_id
            JOIN account_journal journal ON journal.id = move.journal_id
            JOIN res_company company ON company.id = journal.company_id
            JOIN res_currency currency ON currency.id = company.currency_id
            WHERE line.move_id IN %s
            GROUP BY line.move_id, currency.decimal_places
            HAVING ROUND(SUM(line.debit - line.credit), currency.decimal_places) != 0.0;
        ''', [tuple(self.ids)])

        query_res = self._cr.fetchall()
        if query_res:
            ids = [res[0] for res in query_res]
            sums = [res[1] for res in query_res]
            raise UserError(_("Cannot create unbalanced journal entry. Ids: %s\nDifferences debit - credit: %s") % (ids, sums))
    
    # -------------------------------------------------------------------------
    # TAXES METHODS
    # ------------------------------------------------------------------------- 

    def _update_invoice_line_ids(self):
        current_invoice_lines = self.line_ids.filtered(lambda line: not line.exclude_from_invoice_tab)
        others_lines = self.line_ids - current_invoice_lines
        if others_lines and current_invoice_lines - self.invoice_line_ids:
            others_lines[0].recompute_tax_line = True
        self.line_ids = others_lines + self.invoice_line_ids
        self._onchange_recompute_dynamic_lines()

class AccountMoveLineTax(models.Model):
    _name = 'account.move.tax'

    move_id = fields.Many2one('account.move', string='Factura')
    move_line_id = fields.Many2one('account.move.line', string='Linea Contable')
    account_id = fields.Many2one('account.account', string='Cuenta')
    tax_id = fields.Many2one('account.tax', string='Impuesto')
    name = fields.Char(string='Descripción')
    credit = fields.Float(string='Credito')
    debit = fields.Float(string='Debito')
    tax_base_amount = fields.Float(string='Importe Base')
    