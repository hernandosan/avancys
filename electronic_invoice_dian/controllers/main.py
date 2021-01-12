import odoo
from odoo import api, SUPERUSER_ID
import odoo.http as http
from odoo.http import request
import odoo.addons.web.controllers.main as webmain
import json
import os


class AccountInvoiceAck(http.Controller):
    @http.route('/invoice/dian/accept', type='http', auth="public")
    def accept(self, db, token, id):
        registry = odoo.modules.registry.Registry(db)
        state_change = None
        with api.Environment.manage(), registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            invoice_id = env['account.move'].search([
                ('access_token', '=', token),
                ('ei_state', '!=', 'customer_accept'),
                ('id', '=', id)
            ])
            if invoice_id:
                state_change = invoice_id.do_accept()
        if not state_change:
            return
        return request.render('electronic_invoice_dian.customer_accept_invoice', {})

    @http.route('/invoice/dian/reject', type='http', auth="public")
    def reject(self, db, token, id):
        registry = odoo.modules.registry.Registry(db)
        state_change = None
        with api.Environment.manage(), registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            invoice_id = env['account.move'].search([
                ('access_token', '=', token),
                ('ei_state', '!=', 'customer_accept'),
                ('id', '=', id)
            ])
            if invoice_id:
                state_change = invoice_id.do_accept()
        if not state_change:
            return
        return request.render('electronic_invoice_dian.customer_reject_invoice', {})
