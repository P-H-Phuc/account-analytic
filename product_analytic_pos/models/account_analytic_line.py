from odoo import api, fields, models
from odoo.tools import float_compare


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    pos_order_line_id = fields.Many2one("pos.order.line")
    pos_session_id = fields.Many2one("pos.session")

    def _prepare_analytic_lines(self, order_line, analytic_distribution):
        if not analytic_distribution:
            return []

        currency = order_line.currency_id
        analytic_line_vals = []
        distribution_on_each_plan = {}

        for account_ids, distribution in analytic_distribution.items():
            line_values = self._prepare_analytic_distribution_line_from_order_line(
                order_line,
                float(distribution),
                account_ids,
                distribution_on_each_plan,
            )
            if not currency.is_zero(line_values.get("amount")):
                analytic_line_vals.append(line_values)
        self._round_analytic_distribution_line(order_line, analytic_line_vals)
        return analytic_line_vals

    def _prepare_analytic_distribution_line_from_order_line(
        self, order_line, distribution, account_ids, distribution_on_each_plan
    ):
        if not order_line.product_id:
            return {}

        order = order_line.order_id
        product = order_line.product_id
        pos_session = order.session_id
        account_income = product.categ_id.property_account_income_categ_id
        pos_session_move_of_product = (
            pos_session.move_id.line_ids.filtered(
                lambda line: line.account_id == account_income
            )
            if account_income
            else self.env["account.move.line"]
        )
        decimal_precision = self.env["decimal.precision"].precision_get(
            "Percentage Analytic"
        )
        accounts = (
            self.env["account.analytic.account"]
            .browse(map(int, account_ids.split(",")))
            .exists()
        )
        account_field_values = {}
        amount = 0

        for account in accounts:
            distribution_plan = (
                distribution_on_each_plan.get(account.root_plan_id, 0) + distribution
            )
            if (
                float_compare(
                    distribution_plan, 100, precision_digits=decimal_precision
                )
                == 0
            ):  # noqa: E501
                amount = (
                    order_line.price_subtotal_incl
                    * (100 - distribution_on_each_plan.get(account.root_plan_id, 0))
                    / 100.0  # noqa: E501
                )
            else:
                amount = order_line.price_subtotal_incl * distribution / 100.0
            distribution_on_each_plan[account.root_plan_id] = distribution_plan
            account_field_values[account.plan_id._column_name()] = account.id

        return {
            "name": product.display_name,
            "date": order.date_order,
            **account_field_values,
            "partner_id": order.partner_id.id,
            "unit_amount": order_line.qty,
            "product_id": product.id,
            "product_uom_id": order_line.product_uom_id.id,
            "amount": amount,
            "general_account_id": account_income.id if account_income else False,
            "ref": order.name,
            "move_line_id": (
                pos_session_move_of_product
                and pos_session_move_of_product[0].id
                or False
            ),
            "user_id": pos_session.user_id.id,
            "company_id": pos_session.company_id.id or self.env.company.id,
            "category": "other",
            "pos_order_line_id": order_line.id,
            "pos_session_id": pos_session.id,
        }

    def _round_analytic_distribution_line(self, order_line, analytic_lines_vals):
        """Round the analytic lines amount, and cancel the rounding error."""
        if not analytic_lines_vals:
            return

        currency = order_line.currency_id
        rounding_error = 0
        for line in analytic_lines_vals:
            rounded_amount = currency.round(line["amount"])
            rounding_error += rounded_amount - line["amount"]
            line["amount"] = rounded_amount

        # distributing the rounding error
        for line in analytic_lines_vals:
            if currency.is_zero(rounding_error):
                break
            amt = max(
                currency.rounding,
                abs(currency.round(rounding_error / len(analytic_lines_vals))),
            )
            if rounding_error < 0.0:
                line["amount"] += amt
                rounding_error += amt
            else:
                line["amount"] -= amt
                rounding_error -= amt

    @api.model
    def _create_analytic_lines_from_pos_order_lines(self, order_lines):
        analytic_line_vals = []
        for order_line in order_lines:
            product = order_line.product_id
            analytic_distributions = product.analytic_distribution_model_ids.mapped(
                "analytic_distribution"
            )
            for distribution in analytic_distributions:
                analytic_line_vals.extend(
                    self._prepare_analytic_lines(order_line, distribution)
                )
        return self.env["account.analytic.line"].create(analytic_line_vals)
