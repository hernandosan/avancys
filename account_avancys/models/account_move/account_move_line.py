# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    invoice_line_tax_ids = fields.Many2many('account.tax', 'account_invoice_line_tax', 'invoice_line_id', 'tax_id', string='Impuestos')
    ciiu_id = fields.Many2one('res.ciiu', string='CIIU')
    city_id = fields.Many2one('res.city', string='Ciudad')

    def subtotal_per_tax(self, lines, tax, city=False, ciiu=False):
        subtotal = 0
        new_lines = []
        for line in lines:
            if tax in line.tax_ids:
                new_lines.append(line)
            subtotal += sum([x.price_subtotal for x in new_lines])
        return subtotal

    def _get_computed_taxes(self):
        self.ensure_one()

        fposition_obj =  self.env['account.fiscal.position']
        tax_subtotals = {}
        tax_to_return = []
        if self.move_id.is_sale_document(include_receipts=True):
            # Out invoice.
            if self.product_id.taxes_id:
                tax_ids = self.product_id.taxes_id.filtered(lambda tax: tax.company_id == self.move_id.company_id)
            elif self.product_id.categ_id.taxes_id:
                tax_ids = self.product_id.categ_id.taxes_id.filtered(lambda tax: tax.company_id == self.move_id.company_id)
            else:
                tax_ids = self.env['account.tax']
            if not tax_ids and not self.exclude_from_invoice_tab:
                tax_ids = self.move_id.company_id.account_sale_tax_id
        elif self.move_id.is_purchase_document(include_receipts=True):
            # In invoice.
            if self.product_id.supplier_taxes_id:
                tax_ids = self.product_id.supplier_taxes_id.filtered(lambda tax: tax.company_id == self.move_id.company_id)
            elif self.product_id.categ_id.supplier_taxes_id:
                tax_ids = self.product_id.categ_id.supplier_taxes_id.filtered(lambda tax: tax.company_id == self.move_id.company_id)
            else:
                tax_ids = self.env['account.tax']
            if not tax_ids and not self.exclude_from_invoice_tab:
                tax_ids = self.move_id.company_id.account_purchase_tax_id
        else:
            # Miscellaneous operation.
            tax_ids = self.account_id.tax_ids

        if self.company_id and tax_ids:
            tax_ids = tax_ids.filtered(lambda tax: tax.company_id == self.company_id)

        return tax_ids

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if not line.product_id or line.display_type in ('line_section', 'line_note'):
                continue

            line.name = line._get_computed_name()
            line.account_id = line._get_computed_account()
            line.tax_ids = line._get_computed_taxes()
            line.product_uom_id = line._get_computed_uom()
            line.price_unit = line._get_computed_price_unit()

            # Manage the fiscal position after that and adapt the price_unit.
            # E.g. mapping a price-included-tax to a price-excluded-tax must
            # remove the tax amount from the price_unit.
            # However, mapping a price-included tax to another price-included tax must preserve the balance but
            # adapt the price_unit to the new tax.
            # E.g. mapping a 10% price-included tax to a 20% price-included tax for a price_unit of 110 should preserve
            # 100 as balance but set 120 as price_unit.
            if line.tax_ids and line.move_id.fiscal_position_id:
                price_subtotal = line._get_price_total_and_subtotal()['price_subtotal']
                # line.tax_ids = line.move_id.fiscal_position_id.map_tax(
                #     line.tax_ids._origin,
                #     partner=line.move_id.partner_id)
                accounting_vals = line._get_fields_onchange_subtotal(
                    price_subtotal=price_subtotal,
                    currency=line.move_id.company_currency_id)
                amount_currency = accounting_vals['amount_currency']
                business_vals = line._get_fields_onchange_balance(amount_currency=amount_currency)
                if 'price_unit' in business_vals:
                    line.price_unit = business_vals['price_unit']

            # Convert the unit price to the invoice's currency.
            company = line.move_id.company_id
            line.price_unit = company.currency_id._convert(line.price_unit, line.move_id.currency_id, company, line.move_id.date)
