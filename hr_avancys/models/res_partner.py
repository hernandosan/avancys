# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

EMPLOYEE_EMERGENCY_HELP = "Empleado al que este contacto le sirve para alguna emergencia"

LEGAL_STATUS_TYPE = [
    ('natural', 'Persona Natural'),
    ('legal', 'Persona Jurídica')
]


class ResPartner(models.Model):
    _inherit = "res.partner"

    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company, index=True)
    first_name = fields.Char(string='Primer Nombre')
    second_name = fields.Char(string='Segundo Nombre')
    first_surname = fields.Char(string='Primer Apellido')
    second_surname = fields.Char(string='Segundo Apellido')
    ref_num = fields.Char(string='Número de identificación', index=True)
    verification_code = fields.Integer(
        string='Código de verificación', compute="_compute_verification_code", size=1, store=True, readonly=True)
    ref_type_required = fields.Boolean(string='Obligatorio', default=False)
    ref_type_id = fields.Many2one(
        'res.partner.document.type', string='Tipo de identificación')
    legal_status_type = fields.Selection(
        string="Tipo de personería", selection=LEGAL_STATUS_TYPE, default="natural")

    employee = fields.Boolean(
        help="Check this box if this contact is an Employee.", readonly=True)
    employee2emergency_id = fields.Many2one(
        'hr.employee', string="Es contacto de emergencia de", help=EMPLOYEE_EMERGENCY_HELP)
    eps = fields.Boolean(string='Es EPS', default=False,
                         help='Entidad Promotora Salud')
    arl = fields.Boolean(string='Es ARL', default=False,
                         help='Administradora de Riesgos Laborales')
    afp = fields.Boolean(string='Es AFP', default=False,
                         help='Administradora Fondos Pensiones y Cesantias')
    ccf = fields.Boolean(string='Es CCF', default=False,
                         help='Caja Compensacion Familiar')
    eps_code = fields.Char(string='Código de EPS')
    arl_code = fields.Char(string='Código de ARL')
    afp_code = fields.Char(string='Código de AFP')
    ccf_code = fields.Char(string='Código de CCF')

    _sql_constraints = [
        ("ref_num_uniq", "unique (ref_num)",
         "El número de identificación debe ser único por usuario")
    ]

    @api.onchange('first_name', 'second_name', 'first_surname', 'second_surname')
    def _onchange_build_name(self):
        for record in self:
            record.name = record._build_name({})

    def write(self, vals):
        if 'company_type' in vals:
            if vals['company_type'] == 'person':
                vals['name'] = self._build_name(vals)
            elif vals['company_type'] == 'company':
                for field in ['first_name', 'second_name', 'first_surname', 'second_surname']:
                    vals[field] = False
        return super(ResPartner, self).write(vals)

    def _build_name(self, vals):
        tmp_name = ''
        for field in ['first_name', 'second_name', 'first_surname', 'second_surname']:
            data_field = (getattr(self, field)
                          if field not in vals else vals[field]) or ''
            tmp_name += data_field + ' ' if data_field else ''
        return tmp_name.strip()

    @api.depends('name', 'ref_num')
    def _compute_display_name(self):
        """Override completo y cambio de campos trigger del metodo"""
        for record in self:
            if record.ref_num and record.name:
                record.display_name = record._get_name()

    def _get_name(self):
        return ('[%s] ' % self.ref_num if self.ref_num else '') + self.name

    @api.onchange('ref_num')
    def _onchange_ref_num(self):
        for record in self:
            if record.ref_num and len(record.ref_num.strip()) > 0:
                record.ref_type_required = True
            else:
                record.ref_type_required = False

    @api.onchange('eps', 'arl', 'afp', 'ccf')
    def _onchange_eps_arl_afp_ccf(self):
        fields_eval = ['eps', 'arl', 'afp', 'ccf']
        for record in self:
            for fe in fields_eval:
                if not getattr(record, fe):
                    setattr(record, fe+'_code', '')

    @api.depends('ref_num')
    def _compute_verification_code(self):
        prime_numbers = [3, 7, 13, 17, 19, 23,
                         29, 37, 41, 43, 47, 53, 59, 67, 71]
        length_prime_numbers = len(prime_numbers)
        for record in self:
            if not record.ref_num:
                continue
            verification_code = 0
            ref_num = record.ref_num.strip()
            for i, character in enumerate(ref_num[::-1]):
                try:
                    digit = int(character)
                except:
                    raise UserError(
                        'No se puede convertir %s en número' % (ref_num))
                if i >= length_prime_numbers:
                    raise UserError(
                        'Contactar con soporte para poner más números primos')
                verification_code += digit * prime_numbers[i]
            verification_code %= 11
            verification_code = verification_code if verification_code >= 0 else 0
            verification_code = (
                11 - verification_code) if verification_code >= 2 else verification_code
            record.verification_code = verification_code
