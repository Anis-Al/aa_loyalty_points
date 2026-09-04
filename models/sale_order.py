# Part of the aa_loyalty_points module by Anis Alim. Licensed under LGPL-3.

from collections import defaultdict

from odoo import _, fields, models

from .loyalty_program import SPENT_ON_A_LATER_ORDER


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    available_coupon_count = fields.Integer(
        string="Available Coupons",
        compute='_compute_available_coupon_count',
        compute_sudo=True,
    )

    def _get_real_points_for_coupon(self, coupon, post_confirm=False):
        points = super()._get_real_points_for_coupon(coupon, post_confirm=post_confirm)
        if (
            self.state in ('sale', 'done')
            and coupon.program_id.applies_on == SPENT_ON_A_LATER_ORDER
        ):
            points -= sum(
                self.coupon_point_ids.filtered(lambda p: p.coupon_id == coupon).mapped('points')
            )
            points = coupon.currency_id.round(points)
        return points

    def _action_cancel(self):
        self.invoice_ids.filtered(
            lambda move: move.move_type == 'out_refund'
        )._revert_loyalty_refund()
        return super()._action_cancel()

    # === AVAILABLE COUPONS === #

    def _get_available_coupon_domain(self, partners):
        return [
            ('partner_id', 'in', partners.ids),
            ('points', '>', 0),
            ('program_id.active', '=', True),
            '|', ('company_id', '=', False), ('company_id', 'in', self.company_id.ids),
            '|',
                ('expiration_date', '>=', fields.Date.context_today(self)),
                ('expiration_date', '=', False),
        ]

    def _get_available_coupons(self):
        cards_per_order = {order.id: self.env['loyalty.card'] for order in self}
        partners = self.partner_id
        if not partners:
            return cards_per_order

        all_partners = partners.with_context(active_test=False).search(
            [('id', 'child_of', partners.ids)]
        )
        cards = self.env['loyalty.card'].search(
            self._get_available_coupon_domain(all_partners)
        )
        per_partner = defaultdict(lambda: self.env['loyalty.card'])
        for card in cards:
            partner = card.partner_id
            while partner:
                per_partner[(partner.id, card.company_id.id)] |= card
                partner = partner.parent_id

        for order in self:
            used = order.order_line.coupon_id | order.applied_coupon_ids
            if used.filtered(lambda card: not card.program_id.is_nominative):
                continue
            keys = [(order.partner_id.id, False)]
            if order.company_id:
                keys.append((order.partner_id.id, order.company_id.id))
            candidates = self.env['loyalty.card'].union(
                *(per_partner[key] for key in keys)
            )
            cards_per_order[order.id] = candidates.filtered(order._is_coupon_spendable)
        return cards_per_order

    def _is_coupon_spendable(self, card):
        self.ensure_one()
        program = card.program_id
        if program.applies_on == SPENT_ON_A_LATER_ORDER and not program.is_nominative:
            current_id = self.id if isinstance(self.id, int) else float('inf')
            if card.order_id and card.order_id.id >= current_id:
                return False
        return self._get_real_points_for_coupon(card) > 0

    def _compute_available_coupon_count(self):
        cards_per_order = self._get_available_coupons()
        for order in self:
            order.available_coupon_count = len(cards_per_order[order.id])

    def action_view_available_coupons(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Available Coupons"),
            'res_model': 'loyalty.card',
            'view_mode': 'list',
            'views': [(self.env.ref('aa_loyalty_points.loyalty_card_view_list_dialog').id, 'list')],
            'domain': [('id', 'in', self._get_available_coupons()[self.id].ids)],
            'target': 'new',
            'context': {'create': False, 'dialog_size': 'large'},
        }
