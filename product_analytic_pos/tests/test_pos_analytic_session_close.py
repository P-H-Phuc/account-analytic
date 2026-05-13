from odoo import Command
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import TestPointOfSaleCommon


@tagged("post_install", "-at_install")
class TestPosAnalyticSessionClose(TestPointOfSaleCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.analytic_plan = cls.env["account.analytic.plan"].create(
            {
                "name": "Default Plan",
            }
        )
        cls.analytic_account = cls.env["account.analytic.account"].create(
            {
                "name": "Test Analytic",
                "plan_id": cls.analytic_plan.id,
            }
        )
        cls.env["account.analytic.distribution.model"].create(
            {
                "product_id": cls.product_a.id,
                "analytic_distribution": {str(cls.analytic_account.id): 100},
            }
        )

    @classmethod
    def create_pos_order(cls, session, price_unit):
        return cls.PosOrder.create(
            {
                "session_id": session.id,
                "lines": [
                    Command.create(
                        {
                            "product_id": cls.product_a.id,
                            "price_unit": price_unit,
                            "qty": 1,
                            "tax_ids": False,
                            "price_subtotal": price_unit,
                            "price_subtotal_incl": price_unit,
                        }
                    ),
                ],
                "amount_tax": price_unit,
                "amount_total": price_unit,
                "amount_paid": price_unit,
                "amount_return": 0.0,
            }
        )

    @classmethod
    def pay_pos_order(cls, pos_order):
        context_make_payment = {
            "active_ids": pos_order.ids,
            "active_id": pos_order.id,
        }
        pos_make_payment = cls.PosMakePayment.with_context(
            **context_make_payment
        ).create(  # noqa: E501
            {
                "amount": pos_order.amount_total,
            }
        )
        pos_make_payment.with_context(**context_make_payment).check()

    def test_prepare_analytic_lines(self):
        analytic_distributions = self.product_a.analytic_distribution_model_ids.mapped(
            "analytic_distribution"
        )
        self.assertTrue(analytic_distributions)

    def test_create_analytic_lines_from_pos_order_line(self):
        price_unit = 100.0
        self.pos_config.open_ui()
        current_session = self.pos_config.current_session_id

        pos_order = self.create_pos_order(current_session, price_unit)
        self.pay_pos_order(pos_order)
        self.assertEqual(pos_order.state, "paid")
        current_session.post_closing_cash_details(price_unit)
        current_session.close_session_from_ui()
        self.assertEqual(current_session.state, "closed")

        analytic_lines = self.env["account.analytic.line"].search(
            [("pos_session_id", "=", current_session.id)],
        )
        self.assertEqual(len(analytic_lines), 1)
        self.assertEqual(analytic_lines.amount, price_unit)
