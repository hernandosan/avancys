# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class AccountAdvanceCustomer(models.Model):
    _name = 'account.advance.customer'

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @api.depends('amount', 'currency_id', 'exchange_rate')
    def _compute_amount_local(self):
        for record in self:
            record.amount_local = record.amount * record.exchange_rate
    
    def _get_amount_residual(self):
        for record in self:
            remaining = False
            if record.move_id and record.move_line_id:
                remaining = record.move_line_id.amount_residual
            record.remaining = remaining

    name = fields.Char(
        string='Nombre',
        size=64
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Usuario',
        default=lambda self: self.env.user,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Cliente'
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañia',
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Moneda',
    )
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='Cuenta de Anticipo',
    )
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Diario'
    )
    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Comprobante',
    )
    move_line_id = fields.Many2one(
        comodel_name='account.move.line',
        string='Linea a reconciliar',
    )
    full_reconcile_id = fields.Many2one(
        comodel_name='account.full.reconcile',
        string='Conciliación',
        related='move_line_id.full_reconcile_id',
        store=True,
    )
    local_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Moneda Local',
        related='company_id.currency_id',
        store=True,
    )
    sale_id = fields.Many2one(
        comodel_name='sale.order',
        string='Pedido de venta',
    )
    account_analytic_id = fields.Many2one(
        comodel_name='account.analytic.account',
        string='Centro de costo',
    )
    move_nama = fields.Char(
        string='Nombre del comprobante',
    )
    description = fields.Text(
        string='Descripción',
    )
    exchange_rate = fields.Float(
        string='Tasa de Cambio',
        default=1,
    )
    amount = fields.Float(
        string='Valor',
    )
    amount_local = fields.Float(
        string='Valor Moneda Local',
        compute=_compute_amount_local,
        store=True,
    )
    remaining = fields.Float(
        string='Balance',
        compute='_get_amount_residual',
    )
    request_date = fields.Date(
        string='Fecha de solicitud',
    )
    planned_date = fields.Date(
        string='Fecha planificada',
    )
    pay_date = fields.Date(
        string='Fecha de Pago',
    )
    multicurrency = fields.Boolean(
        string='Multimoneda',
    )
    crossed = fields.Boolean(
        string='Cruzado',
    )
    state = fields.Selection(
        string='Estado',
        selection=[
            ('draft', 'Borrador'),
            ('waiting_approval', 'Pendiente Aprobacion'), 
            ('validated', 'Aprobado'), 
            ('posted', 'Contabilizado'),  
            ('refused', 'Rechazado'),
            ('cancelled', 'Cancelado'),
        ],
        default='draft',
    )

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------

    def validate_rate(self):
        for record in self:
            if record.pay_date:
                if record.currency_id != record.company_id.currency_id:
                    rates = record.currency_id._get_rate(record.company_id, record.pay_date)
                    if not rates:
                        raise UserError('No se ha establecido una tasa para la fecha de pago %s' % (record.pay_date))
                    record.exchange_rate = rates[0]
            else:
                raise UserError('Por favor ingrese una fecha de pago')

    # -------------------------------------------------------------------------
    # STATE METHODS
    # -------------------------------------------------------------------------

    def action_draft(self):
        for record in self:
            record.write({'state': 'draft'})
    
    def action_waiting_approval(self):
        for record in self:
            record.write({'state': 'waiting_approval'})
    
    def action_validated(self):
        for record in self:
            record.write({'state': 'validated'})
    
    def action_cancelled(self):
        for record in self:
            record.write({'state': 'cancelled'})
    
    def action_refused(self):
        for record in self:
            record.write({'state': 'refused'})
    
    def action_posted(self):
        for record in self:
            if record.move_id:
                record.write({'state': 'posted'})
                continue
            # Validaciones
            record.validate_rate()
            if not record.pay_date:
                raise UserError('Por favor ingrese la fecha de pago')
            if not record.partner_id.property_account_advance_customer_id:
                raise UserError('El tercero no tiene una cuenta de pago para anticipos configurada')
            # Información
            date = record.pay_date
            currency = (record.currency_id != record.local_currency_id) and record.currency_id or False
            currency_qty = currency and record.amount or False
            amount = currency and record.amount * record.exchange_rate or record.amount
            account_advance_customer_id = record.partner_id.property_account_advance_customer_id.id
            partner_id = record.partner_id.id
            # Asiento
            vals = {
                'partner_id': partner_id,
                'journal_id': record.journal_id.id,
                'date': date,
                'ref': record.name,
            }
            move_id = self.env['account.move'].create(vals)
            db_line = {
                'partner_id': partner_id,
                'currency_id': currency and currency.id or False,
                'amount_currency': currency_qty,
                'journal_id': record.journal_id.id,
                'date': date,
                'name': record.name,
                'debit': 0,
                'credit': amount,
                'account_id': account_advance_customer_id,
                'analytic_account_id': record.account_analytic_id and record.account_analytic_id.id or False,
                'move_id': move_id.id,
            }
            db_move_line_id = self.env['account.move.line'].create(db_line)
            cr_line = db_line
            cr_line.update({
                'amount_currency': currency_qty * -1,
                'debit': amount,
                'credit': 0,
                'account_id': record.journal_id.default_account_id.id,
            })
            cr_move_line_id = self.env['account.move.line'].create(cr_line)
            if move_id.state == 'draft':
                move_id.action_post()
            # Actualizar Anticipo
            record.write({
                'move_id': move_id.id,
                'move_line_id': db_move_line_id.id,
                'state': 'posted'
            })
    
    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for record in self:
            if record.partner_id:
                if record.partner_id.property_account_advance_customer_id:
                    record.update({'account_id': record.partner_id.property_account_advance_customer_id.id})
    
    @api.onchange('sale_id')
    def _onchange_sale_id(self):
        for record in self:
            if record.sale_id:
                amount = 0
                pass
    
    @api.onchange('payment_mode_id')
    def _onchange_payment_mode_id(self):
        for record in self:
            if record.payment_mode_id:
                if record.payment_mode_id.journal_id:
                    record.update({'journal_bank_id': record.payment_mode_id.journal_id.id})
    
    # -------------------------------------------------------------------------
    # CONSTRAIN METHODS
    # -------------------------------------------------------------------------

    @api.constrains('amount')
    def _check_amoun(self):
        for record in self:
            if record.amount <= 0:
                raise UserError('El valor del anticipo debe ser mayor a cero')
    
    @api.constrains('exchange_rate')
    def _check_exchange_rate(self):
        for record in self:
            if record.exchange_rate < 0 and record.state != 'draft':
                raise UserError('No existe una tasa con la cual se pueda evaluar')
    
    # -------------------------------------------------------------------------
    # LOW-LEVEL METHODS
    # -------------------------------------------------------------------------
    
    @api.model
    def create(self, vals):
        sequence_id = self.env['ir.sequence'].search([('code','=','account.advance.customer.sequence')], limit=1)
        vals['name'] = sequence_id.next_by_id()
        return super().create(vals)
    
    def copy(self, default=None):
        default = dict(default or {})
        default['move_id'] = False
        return super().copy(default)