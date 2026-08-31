# Part of the aa_loyalty_points module by Anis Alim. Licensed under LGPL-3.

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestPortalLoyalty(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['loyalty.program'].search([]).sudo().write({'active': False})

        cls.points_program = cls.env['loyalty.program'].create({
            'name': "Portal Points",
            'program_type': 'loyalty',
        })
        cls.wallet_program = cls.env['loyalty.program'].create({
            'name': "Portal Wallet",
            'program_type': 'ewallet',
        })
        cls.points_program.portal_point_name = "Points"
        cls.wallet_program.portal_point_name = "Credits"

        cls.alice = cls._create_portal_user('alice')
        cls.bob = cls._create_portal_user('bob')
        cls.carol = cls._create_portal_user('carol')

        cls.alice_points_card = cls.env['loyalty.card'].create({
            'program_id': cls.points_program.id,
            'partner_id': cls.alice.partner_id.id,
            'points': 100,
        })
        cls.alice_wallet_card = cls.env['loyalty.card'].create({
            'program_id': cls.wallet_program.id,
            'partner_id': cls.alice.partner_id.id,
            'points': 50,
        })
        cls.bob_card = cls.env['loyalty.card'].create({
            'program_id': cls.points_program.id,
            'partner_id': cls.bob.partner_id.id,
            'points': 7,
        })
        cls.env['loyalty.history'].create([
            {
                'card_id': cls.alice_points_card.id,
                'description': "ALICE MOVEMENT",
                'issued': 100,
                'used': 0,
            },
            {
                'card_id': cls.bob_card.id,
                'description': "BOB MOVEMENT",
                'issued': 7,
                'used': 0,
            },
        ])

    # === HELPERS === #

    @classmethod
    def _create_portal_user(cls, name):
        return cls.env['res.users'].create({
            'name': name.capitalize(),
            'login': f'portal_loyalty_{name}',
            'password': f'portal_loyalty_{name}',
            'email': f'{name}@example.com',
            'group_ids': [Command.set([cls.env.ref('base.group_portal').id])],
        })

    def _login(self, name):
        self.env.flush_all()
        self.authenticate(f'portal_loyalty_{name}', f'portal_loyalty_{name}')

    def _counter(self):
        return self.make_jsonrpc_request('/my/counters', {'counters': ['loyalty_count']})

    # === TESTS === #

    def test_customer_without_a_card_is_redirected_away(self):
        self._login('carol')

        response = self.url_open('/my/loyalty', allow_redirects=False)

        self.assertIn(response.status_code, (301, 302, 303))
        self.assertTrue(response.headers['Location'].endswith('/my'))

    def test_customer_without_a_card_has_a_zero_counter(self):
        self._login('carol')

        self.assertEqual(self._counter()['loyalty_count'], 0)

    def test_the_history_is_on_the_page_itself(self):
        self._login('alice')

        html = self.url_open('/my/loyalty').text

        self.assertIn("ALICE MOVEMENT", html)
        self.assertIn("Document", html)
        self.assertIn("Earned", html)
        self.assertIn("Used", html)

    def test_two_programs_give_two_separate_subtotals(self):
        self._login('alice')

        html = self.url_open('/my/loyalty').text

        self.assertEqual(html.count('o_loyalty_total'), 2)
        self.assertIn("100 Points", html)
        self.assertIn("50 Credits", html)
        self.assertNotIn("150 Points", html)

    def test_the_card_code_is_masked(self):
        self._login('alice')

        html = self.url_open('/my/loyalty').text

        self.assertIn(self.alice_points_card.code[-4:], html)
        self.assertNotIn(self.alice_points_card.code, html)

    def test_a_customer_cannot_read_another_customers_card_history(self):
        self._login('alice')

        response = self.url_open(
            f'/my/loyalty_card/{self.bob_card.id}/history', allow_redirects=False
        )

        self.assertIn(response.status_code, (301, 302, 303))

    def test_the_consolidated_history_only_shows_own_movements(self):
        self._login('alice')

        html = self.url_open('/my/loyalty').text

        self.assertIn("ALICE MOVEMENT", html)
        self.assertNotIn("BOB MOVEMENT", html)

    def test_an_expired_card_counts_neither_in_the_counter_nor_the_total(self):
        self.env['loyalty.card'].create({
            'program_id': self.wallet_program.id,
            'partner_id': self.alice.partner_id.id,
            'points': 999,
            'expiration_date': fields.Date.today() - relativedelta(days=1),
        })
        self._login('alice')

        html = self.url_open('/my/loyalty').text

        self.assertEqual(self._counter()['loyalty_count'], 2)
        self.assertIn("50 Credits", html)
        self.assertNotIn("1049 Credits", html)

    def test_an_archived_program_is_excluded(self):
        self.wallet_program.active = False
        self._login('alice')

        html = self.url_open('/my/loyalty').text

        self.assertEqual(self._counter()['loyalty_count'], 1)
        self.assertEqual(html.count('o_loyalty_total'), 1)
        self.assertNotIn("50 Credits", html)

    def test_the_native_sidebar_is_not_broken(self):
        self._login('alice')

        html = self.url_open('/my').text

        self.assertIn('o_loyalty_container', html)
        self.assertIn('/my/loyalty', html)

    def test_a_next_order_coupon_shows_in_the_portal(self):
        program = self.env['loyalty.program'].create({
            'name': "Portal Coupons",
            'program_type': 'next_order_coupons',
            'applies_on': 'future',
            'trigger': 'auto',
        })
        program.portal_point_name = "Coupon points"
        card = self.env['loyalty.card'].create({
            'program_id': program.id,
            'partner_id': self.alice.partner_id.id,
            'points': 75,
        })
        self._login('alice')

        html = self.url_open('/my/loyalty').text

        self.assertEqual(self._counter()['loyalty_count'], 3)
        self.assertEqual(html.count('o_loyalty_total'), 3)
        self.assertIn("75 Coupon points", html)
        self.assertIn(card.code[-4:], html)

    def test_the_sidebar_shows_the_same_programs_as_the_page(self):
        program = self.env['loyalty.program'].create({
            'name': "Portal Coupons",
            'program_type': 'next_order_coupons',
            'applies_on': 'future',
            'trigger': 'auto',
        })
        self.env['loyalty.card'].create({
            'program_id': program.id,
            'partner_id': self.alice.partner_id.id,
            'points': 75,
        })
        self._login('alice')

        html = self.url_open('/my').text

        self.assertIn("Portal Coupons", html)
        self.assertIn('/aa_loyalty_points/static/src/img/voucher.svg', html)
        self.assertNotIn('/loyalty/static/src/img/next_order_coupons.svg', html)
