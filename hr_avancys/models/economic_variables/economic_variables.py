# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


def check_search(var, message, condition):
    if not var:
        return 0
    elif len(var) > 1:
        raise ValidationError(
            f"Se encontraron {len(var)} {message} {condition}")
    else:
        return 1


class EconomicVariables(models.Model):
    _name = 'economic.variable'
    _description = 'Variable económica'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True, readonly=True)
    code = fields.Char(string='Código', required=True, readonly=True)
    active = fields.Boolean(string='Activo', default=True)
    company_id = fields.Many2one(comodel_name='res.company', string='Compañia',
                                 default=lambda self: self.env.company)
    compute_value = fields.Boolean(
        string='Valor calculado', default=False,
        help="Aplica principalmente para la tabla de retención en la fuente")
    variable_line_ids = fields.One2many(
        comodel_name='economic.variable.line', inverse_name='variable_id',
        string='Líneas de variable económica')

    _sql_constraints = [
        ("variable_uniq", "unique (company_id, code)",
         "Ya está definida la variable económica.")
    ]

    @api.model
    def get_value(self, code, year):
        variable = self.search(
            [('active', '=', True), ('code', '=', code)])
        res = check_search(
            variable, "variables economicas con el código", code)
        if not res:
            return res
        year = str(year) if type(year) == int else year
        line = list(filter(lambda l: l.year == year,
                           variable.variable_line_ids))
        res = check_search(
            line, "Líneas de variable económica con el año", year)
        if not res:
            return res
        elif not variable.compute_value:
            return line[0].value
        else:
            table = []
            for detail in line[0].variable_line_detail_ids:
                table.append(
                    (detail.subtract, detail.rate, detail.add,
                     detail.lower_limit if detail.has_lower_limit else None,
                     detail.upper_limit if detail.has_upper_limit else None)
                )
            return table

    def _get_economic_variables(self, economic_variables, year):
        for ev in economic_variables:
            if year not in economic_variables[ev]:
                economic_variables[ev][year] = self.get_value(ev, year)
