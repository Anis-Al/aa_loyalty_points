# Part of the aa_loyalty_points module by Anis Alim. Licensed under LGPL-3.

import logging

from odoo import _, models
from odoo.tools import float_round

from .loyalty_program import BALANCE_PROGRAM_TYPES

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        posted.filtered(lambda move: move.move_type == 'out_refund')._apply_loyalty_refund()
        return posted

    def button_draft(self):
        self._revert_loyalty_refund()
        return super().button_draft()

    def button_cancel(self):
        self._revert_loyalty_refund()
        return super().button_cancel()

    # === LOYALTY POINTS === #

    def _apply_loyalty_refund(self):
        History = self.env['loyalty.history'].sudo()
        for move in self:
            if History.search_count(
                [('order_model', '=', 'account.move'), ('order_id', '=', move.id)], limit=1
            ):
                continue

            orders = move.invoice_line_ids.sale_line_ids.order_id
            if not orders:
                _logger.info(
                    "Credit note %s is not linked to any sales order, loyalty points left untouched.",
                    move.name,
                )
                continue

            history_vals = []
            for order in orders:
                ratio = move._get_loyalty_refund_ratio(order)
                if ratio:
                    history_vals += move._apply_loyalty_refund_on_order(order, ratio)
            History.create(history_vals)

    def _revert_loyalty_refund(self):
        history = self.env['loyalty.history'].sudo().search([
            ('order_model', '=', 'account.move'),
            ('order_id', 'in', self.ids),
        ])
        for line in history:
            card = line.card_id
            card.points -= line.issued - line.used
            if not card.active and card.points > 0:
                card.action_unarchive()
        history.unlink()

    def _get_loyalty_refund_ratio(self, order):
        self.ensure_one()
        base = sum(
            order.order_line.filtered(lambda line: not line.is_reward_line).mapped('price_subtotal')
        )
        if order.currency_id.is_zero(base):
            return 0.0
        refunded = sum(
            line.price_subtotal
            for line in self.invoice_line_ids
            if order in line.sale_line_ids.order_id
            and not any(line.sale_line_ids.mapped('is_reward_line'))
        )
        if self.currency_id != order.currency_id:
            refunded = self.currency_id._convert(
                refunded, order.currency_id, self.company_id, self.invoice_date or self.date
            )
        return min(max(refunded / base, 0.0), 1.0)

    def _apply_loyalty_refund_on_order(self, order, ratio):
        self.ensure_one()
        order_history = self.env['loyalty.history'].sudo().search([
            ('order_model', '=', 'sale.order'),
            ('order_id', '=', order.id),
        ])
        history_vals = []
        for line in order_history:
            card = line.card_id
            program = card.program_id
            if program.program_type not in BALANCE_PROGRAM_TYPES or program.refund_policy == 'none':
                continue
            share = 1.0 if program.refund_policy == 'full' else ratio
            taken = float_round(share * line.issued, precision_digits=2, rounding_method='DOWN')
            given = float_round(share * line.used, precision_digits=2, rounding_method='UP')
            if not program.allow_negative_points:
                capped = min(taken, max(card.points + given, 0.0))
                if capped < taken:
                    card.message_post(body=_(
                        "Credit note %(refund)s: %(shortfall)s could not be taken back,"
                        " the balance was insufficient.",
                        refund=self.name,
                        shortfall=card._format_points(taken - capped),
                    ))
                    taken = capped
            if not taken and not given:
                continue
            card.points += given - taken
            if (
                not program.is_nominative
                and card.order_id == order
                and not card.use_count
                and card.points <= 0
            ):
                card.action_archive()
            history_vals.append({
                'card_id': card.id,
                'order_model': 'account.move',
                'order_id': self.id,
                'description': _(
                    "Credit note %(refund)s on order %(order)s",
                    refund=self.name,
                    order=order.name,
                ),
                'issued': given,
                'used': taken,
            })
        return history_vals
