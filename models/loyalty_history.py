# Part of the aa_loyalty_points module by Anis Alim. Licensed under LGPL-3.

from odoo import models


class LoyaltyHistory(models.Model):
    _inherit = 'loyalty.history'

    def _get_order_portal_url(self):
        self.ensure_one()
        if self.order_model == 'account.move':
            move = self.env['account.move'].browse(self.order_id).exists()
            return move.get_portal_url() if move else False
        return super()._get_order_portal_url()
