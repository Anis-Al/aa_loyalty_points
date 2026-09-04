# Part of the aa_loyalty_points module by Anis Alim. Licensed under LGPL-3.

from dateutil.relativedelta import relativedelta

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCardExpiry(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': "Jean Jacques"})
        cls.discount_program = cls.env['loyalty.program'].create({
            'name': "Next order coupon",
            'program_type': 'next_order_coupons',
        })
        cls.loyalty_program = cls.env['loyalty.program'].create({
            'name': "Loyalty card",
            'program_type': 'loyalty',
        })
        cls.ewallet_program = cls.env['loyalty.program'].create({
            'name': "Wallet",
            'program_type': 'ewallet',
        })

    def _card(self, program):
        return self.env['loyalty.card'].create({
            'program_id': program.id,
            'partner_id': self.partner.id,
            'points': 100,
        })

    def test_a_discount_code_expires_twelve_months_after_creation(self):
        card = self._card(self.discount_program)
        self.assertEqual(
            card.expiration_date,
            card.create_date.date() + relativedelta(months=12),
        )

    def test_a_loyalty_card_expires_twelve_months_after_creation(self):
        card = self._card(self.loyalty_program)
        self.assertEqual(
            card.expiration_date,
            card.create_date.date() + relativedelta(months=12),
        )

    def test_an_ewallet_card_keeps_no_expiration_date(self):
        self.assertFalse(self._card(self.ewallet_program).expiration_date)

    def test_an_explicit_expiration_date_is_kept(self):
        given = self.env.cr.now().date() + relativedelta(days=30)
        card = self.env['loyalty.card'].create({
            'program_id': self.discount_program.id,
            'partner_id': self.partner.id,
            'points': 100,
            'expiration_date': given,
        })
        self.assertEqual(card.expiration_date, given)
