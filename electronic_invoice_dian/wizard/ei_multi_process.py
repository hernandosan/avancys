# -*- coding: utf-8 -*-
from openerp import models, fields, api


class EIMultiProcess(models.TransientModel):
    _name = 'ei.multi.process'

    @api.onchange('invoices')
    def populate_invoices(self):
        invoices = self.env['account.move'].browse(
            self._context['active_ids'])
        txt = ''
        for invoice in invoices.filtered(
                lambda invoice: invoice.move_type in (
                    'out_invoice', 'out_refund')
                and invoice.state == 'posted'
                and invoice.ei_state in ('pending', 'dian_reject')):
            txt += invoice.name + '\n'
        self.invoices = txt

    invoices = fields.Text(string='Facturas por Procesar', readonly=True,
                           help="Facturas con Estado 'No Transferido'")

    def send_multiple_invoices(self):
        active_invoices = self.env['account.move'].browse(
            self._context['active_ids'])
        to_send_invoices = active_invoices.filtered(
            lambda invoice: invoice.move_type in ('out_invoice', 'out_refund')
            and invoice.state == 'posted'
            and invoice.ei_state in ('pending', 'dian_reject'))
        if not to_send_invoices:
            return
        if self.env.user.company_id.invoice_batch_process:
            ei_batch_process = self.env['ei.batch.process']
            ei_batch_process.process_batch(to_send_invoices)
        else:
            for invoice in to_send_invoices:
                invoice.generate_electronic_invoice()
