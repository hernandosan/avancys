# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

ADDRESS_HOME_ID_HELP = """
Enter here the private address of the employee, not the one linked to your company.
"""


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    partner_id = fields.Many2one(
        comodel_name='res.partner', string='Contacto', required="1",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    name = fields.Char(string="Nombre", related='partner_id.name',
                       store=True, readonly=False, tracking=True)
    user_id = fields.Many2one(
        'res.users', related='', compute="_compute_res_user", store=True, readonly=True)
    active = fields.Boolean(
        'Active', related='partner_id.active', default=True, store=True, readonly=False)
    address_home_id = fields.Many2one(
        'res.partner', 'Address', tracking=True, store=True,
        related="partner_id", help=ADDRESS_HOME_ID_HELP)
    country_partner_id = fields.Many2one(
        'res.country', string="País", related="partner_id.country_id")
    state_partner_id = fields.Many2one(
        'res.country.state', string="Departamento", related="partner_id.state_id")
    city_partner_id = fields.Many2one(
        'res.city', string="Ciudad", related="partner_id.city_id")
    street = fields.Char(related="partner_id.street", readonly=False)
    street2 = fields.Char(related="partner_id.street2", readonly=False)
    phone = fields.Char(related='partner_id.phone',
                        related_sudo=False, string="Private Phone")
    private_email = fields.Char(
        related='partner_id.email', string="Private Email")
    emergency_contact_ids = fields.One2many(
        comodel_name='res.partner', inverse_name='employee2emergency_id', string='Contactos de emergencia')
    bank_account_id = fields.Many2one(
        'res.partner.bank', 'Cuenta Bancaria',
        domain="[('partner_id', '=', partner_id), ('company_id', '=', company_id)]",
        tracking=True, help='Employee bank salary account')
    identification_id = fields.Char(
        string='Identification No', related='partner_id.ref_num', tracking=True)

    # Campo Obsoleto pero se sebe mantener esta definicion por el related
    user_partner_id = fields.Many2one(
        comodel_name='res.users', related='', related_sudo=False, string="User's partner")
    # Campo Obsoleto, se quita restriccion not null
    resource_id = fields.Many2one('resource.resource', required=False)

    _sql_constraints = [
        ("partner_id_uniq", "unique (partner_id)",
         "El contacto debe ser único por empleado")
    ]

    @api.model
    def create(self, vals):
        if 'partner_id' not in vals:
            raise UserError(_('El empleado debe tener contacto relacionado.'))
        partner_id = self.env['res.partner'].browse(vals['partner_id'])
        partner_id.write({'employee': True})
        vals['name'] = partner_id.name
        return super(models.Model, self).create(vals)

    @api.depends('partner_id')
    def _compute_res_user(self):
        for record in self:
            if not record.partner_id:
                continue
            self._cr.execute(
                'select id from res_users where partner_id = %s', (record.partner_id.id,))
            res = self._cr.fetchall()
            record.user_id = self.env['res.users'].browse(
                res[0][0]) if len(res) == 1 else False

    def write(self, vals):
        for record in self:
            if 'partner_id' in vals:
                partner_id = self.env['res.partner'].browse(vals['partner_id'])
                if partner_id:
                    partner_id.write({'employee': True})
                if record.partner_id:
                    record.partner_id.write({'employee': False})
        return super(HrEmployee, self).write(vals)
