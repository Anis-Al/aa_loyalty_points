# Part of the aa_loyalty_points module by Anis Alim. Licensed under LGPL-3.

from odoo import fields
from odoo.http import request, route

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager

from ..models.loyalty_program import BALANCE_PROGRAM_TYPES


class CustomerPortalLoyaltyPoints(CustomerPortal):

    def _get_portal_loyalty_card_domain(self):
        return [
            ('partner_id', '=', request.env.user.partner_id.id),
            ('program_id.active', '=', True),
            ('program_id.program_type', 'in', list(BALANCE_PROGRAM_TYPES)),
            '|',
                ('expiration_date', '>=', fields.Date.today()),
                ('expiration_date', '=', False),
        ]

    def _get_portal_loyalty_cards(self):
        return request.env['loyalty.card'].sudo().search(
            self._get_portal_loyalty_card_domain(), order='program_id, id'
        )

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'loyalty_count' in counters:
            values['loyalty_count'] = request.env['loyalty.card'].sudo().search_count(
                self._get_portal_loyalty_card_domain()
            )
        if not counters:
            values['cards_per_programs'] = dict(request.env['loyalty.card'].sudo()._read_group(
                domain=self._get_portal_loyalty_card_domain(),
                groupby=['program_id'],
                aggregates=['id:recordset'],
            ))
        return values

    @route(
        ['/my/loyalty', '/my/loyalty/page/<int:page>'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_my_loyalty(self, page=1, **kw):
        cards_sudo = self._get_portal_loyalty_cards()
        if not cards_sudo:
            return request.redirect('/my')

        totals = {}
        for card in cards_sudo:
            total = totals.setdefault(card.point_name or '', {'points': 0.0, 'card': card})
            total['points'] += card.points

        LoyaltyHistorySudo = request.env['loyalty.history'].sudo()
        domain = [('card_id', 'in', cards_sudo.ids)]
        pager = portal_pager(
            url='/my/loyalty',
            total=LoyaltyHistorySudo.search_count(domain),
            page=page,
            step=self._items_per_page,
        )
        history_lines = LoyaltyHistorySudo.search(
            domain,
            limit=self._items_per_page,
            offset=pager['offset'],
        )

        return request.render('aa_loyalty_points.portal_my_loyalty', {
            'cards': cards_sudo,
            'totals': totals,
            'pager': pager,
            'history_lines': history_lines,
            'page_name': 'loyalty_points',
        })
