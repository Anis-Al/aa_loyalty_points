# Part of the aa_loyalty_points module by Anis Alim. Licensed under LGPL-3.

from collections import defaultdict

from odoo import _, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    available_coupon_count = fields.Integer(
        string="Available Coupons",
        compute='_compute_available_coupon_count',
        compute_sudo=True,
    )

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

    def _compute_available_coupon_count(self):
        self.available_coupon_count = 0
        partners = self.partner_id
        if not partners:
            return

        all_partners = partners.with_context(active_test=False).search(
            [('id', 'child_of', partners.ids)]
        )
        groups = self.env['loyalty.card']._read_group(
            domain=self._get_available_coupon_domain(all_partners),
            groupby=['partner_id', 'company_id'],
            aggregates=['__count'],
        )
        counts = defaultdict(int)
        for partner, company, count in groups:
            while partner:
                counts[(partner.id, company.id)] += count
                partner = partner.parent_id

        for order in self:
            total = counts[(order.partner_id.id, False)]
            if order.company_id:
                total += counts[(order.partner_id.id, order.company_id.id)]
            order.available_coupon_count = total

    def action_view_available_coupons(self):
        self.ensure_one()
        all_partners = self.partner_id.with_context(active_test=False).search(
            [('id', 'child_of', self.partner_id.ids)]
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _("Available Coupons"),
            'res_model': 'loyalty.card',
            'view_mode': 'list',
            'views': [(self.env.ref('aa_loyalty_points.loyalty_card_view_list_dialog').id, 'list')],
            'domain': self._get_available_coupon_domain(all_partners),
            'target': 'new',
            'context': {'create': False, 'dialog_size': 'large'},
        }
