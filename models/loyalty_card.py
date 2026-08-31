# Part of the aa_loyalty_points module by Anis Alim. Licensed under LGPL-3.

from odoo import models
from odoo.tools import formatLang

from .loyalty_program import BALANCE_PROGRAM_TYPES

DEFAULT_STATEMENT_MAX_LINES = 50


class LoyaltyCard(models.Model):
    _inherit = 'loyalty.card'

    def _shows_points_statement(self):
        self.ensure_one()
        return self.program_id.program_type in BALANCE_PROGRAM_TYPES

    def _get_points_money_value(self):
        self.ensure_one()
        reward = self.program_id.reward_ids.filtered(
            lambda r: r.reward_type == 'discount' and r.discount_mode == 'per_point'
        )[:1]
        if not reward or reward.discount in (0, 1):
            return ''
        return formatLang(
            self.env,
            self.points * reward.discount,
            currency_obj=self.program_id.currency_id,
        )

    def _get_statement_history(self):
        self.ensure_one()
        if not self._shows_points_statement():
            return self.env['loyalty.history']
        limit = int(self.env['ir.config_parameter'].sudo().get_param(
            'aa_loyalty_points.statement_max_lines', DEFAULT_STATEMENT_MAX_LINES
        ))
        return self.history_ids[:limit] if limit > 0 else self.history_ids
