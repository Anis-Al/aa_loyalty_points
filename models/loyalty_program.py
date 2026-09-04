# Part of the aa_loyalty_points module by Anis Alim. Licensed under LGPL-3.

from odoo import fields, models

BALANCE_PROGRAM_TYPES = ('loyalty', 'gift_card', 'ewallet', 'next_order_coupons')
SPENT_ON_A_LATER_ORDER = 'future'


class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    refund_policy = fields.Selection(
        selection=[
            ('proportional', "Proportional to the refunded amount"),
            ('full', "Full, on the first credit note"),
            ('none', "No recovery"),
        ],
        string="Points on Credit Note",
        default='proportional',
        required=True,
        help="What happens to the points when a customer credit note is posted on"
             " an order that earned or spent points.",
    )
    allow_negative_points = fields.Boolean(
        string="Allow a Negative Balance",
        help="If unchecked, taking points back on a credit note is capped at the"
             " available balance and the shortfall is logged on the card.",
    )
