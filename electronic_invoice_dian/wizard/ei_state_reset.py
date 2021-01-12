# -*- coding: utf-8 -*-
from openerp import models, fields, api


class EIStateReset(models.TransientModel):
    _name = 'ei.state.reset'

    def reset_ei_state(self):
        self.env['account.move'].browse(
            self._context['active_id']).ei_state = 'pending'
