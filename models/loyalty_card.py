# Part of the aa_loyalty_points module by Anis Alim. Licensed under LGPL-3.

from odoo import models

from .loyalty_program import BALANCE_PROGRAM_TYPES

DEFAULT_STATEMENT_MAX_LINES = 50


class LoyaltyCard(models.Model):
    _inherit = 'loyalty.card'

    def _shows_points_statement(self):
        self.ensure_one()
        return self.program_id.program_type in BALANCE_PROGRAM_TYPES

    def _get_statement_history(self):
        self.ensure_one()
        if not self._shows_points_statement():
            return self.env['loyalty.history']
        limit = int(self.env['ir.config_parameter'].sudo().get_param(
            'aa_loyalty_points.statement_max_lines', DEFAULT_STATEMENT_MAX_LINES
        ))
        return self.history_ids[:limit] if limit > 0 else self.history_ids
