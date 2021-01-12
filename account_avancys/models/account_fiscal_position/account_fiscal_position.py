# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, Warning


class AccountFiscalPositionTax(models.Model):
    _inherit = 'account.fiscal.position'
    
    def map_tax2(self, fposition, taxes_to_map, partner_id, city_id, ciiu, move_id=False):
        if not fposition:
            raise ValidationError('Configure la posicion Fiscal del tercero')
        ciiu_ica = (bool)(self.env['ir.config_parameter'].sudo().get_param('account_avancys.ciiu_ica'))
        result = []

        if ciiu_ica:
            if taxes_to_map:
                for t in taxes_to_map.keys():
                    if not t.check_lines and t.child_cities_ids:
                        raise Warning("En uno de los impuestos configurados tiene calculo especial pero no tiene "
                                      "activada la opcion de validacion por lineas")
                    found = False
                    subtotal = taxes_to_map[t]
                    # City verify mapping
                    if t.parent_city_id:
                        if t.city_id != city_id:
                            if city_id:
                                for child in t.parent_city_id.child_cities_ids:
                                    if child.city_id == city_id and ciiu in child.ciiu_ids:
                                        t = child
                                        found = True
                                        break
                            if not found:
                                t = t.parent_city_id
                    # Value mapping
                    delete = False
                    if move_id:
                        if not move_id.is_return_document():
                            for mapp in fposition.tax_ids:
                                if mapp.tax_src_id and mapp.tax_src_id.id == t.id and mapp.option:
                                    if mapp.option == 'always' or (mapp.option == 'great' and subtotal > mapp.value) or (mapp.option == 'great_equal' and subtotal >= mapp.value) or (mapp.option == 'equal' and subtotal == mapp.value) or (mapp.option == 'minor' and subtotal < mapp.value) or (mapp.option == 'minor_equal' and subtotal <= mapp.value):
                                        if not mapp.tax_dest_id:
                                            delete = True
                                            break
                                        t = mapp.tax_dest_id
                    # City mapping
                    if not delete and t.child_cities_ids:
                        delete = True
                        for child in t.child_cities_ids:
                            if child.city_id == city_id and ciiu in child.ciiu_ids:
                                t = child
                                delete = False
                                break

                    if not delete:
                        result.append(t.id)
        else:
            if taxes_to_map:
                for t in taxes_to_map.keys():
                    found = False
                    subtotal = taxes_to_map[t]
                    # City verify mapping
                    if t.parent_city_id:
                        if t.city_id != city_id:
                            if city_id:
                                for child in t.parent_city_id.child_cities_ids:
                                    if child.city_id == city_id:
                                        t = child
                                        found = True
                                        break
                            if not found:
                                t = t.parent_city_id
                    # Value mapping
                    delete = False
                    if move_id:
                        if not move_id.is_return_document():
                            for mapp in fposition.tax_ids:
                                if mapp.tax_src_id and mapp.tax_src_id.id == t.id and mapp.option:
                                    if mapp.option == 'always' or (mapp.option == 'great' and subtotal > mapp.value) or ( mapp.option == 'great_equal' and subtotal >= mapp.value) or (mapp.option == 'equal' and subtotal == mapp.value) or (mapp.option == 'minor' and subtotal < mapp.value) or (mapp.option == 'minor_equal' and subtotal <= mapp.value):
                                        if not mapp.tax_dest_id:
                                            delete = True
                                            break
                                        t = mapp.tax_dest_id
                    # City mapping
                    if not delete and t.child_cities_ids:
                        delete=True
                        for child in t.child_cities_ids:
                            if child.city_id == city_id:
                                t = child
                                ok = True
                                delete = False
                                break
                    if not delete:
                        result.append(t.id)
        return result
