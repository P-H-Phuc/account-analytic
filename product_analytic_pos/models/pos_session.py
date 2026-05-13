from odoo import models


class PosSession(models.Model):
    _inherit = "pos.session"

    def action_pos_session_close(
        self,
        balancing_account=False,
        amount_to_balance=0,
        bank_payment_method_diffs=None,
    ):
        result = super().action_pos_session_close(
            balancing_account, amount_to_balance, bank_payment_method_diffs
        )
        self._create_account_analytic_lines_at_close_session()
        return result

    def _create_account_analytic_lines_at_close_session(self):
        self.ensure_one()
        order_lines = self._get_closed_orders().mapped("lines")
        self.env["account.analytic.line"]._create_analytic_lines_from_pos_order_lines(
            order_lines
        )
