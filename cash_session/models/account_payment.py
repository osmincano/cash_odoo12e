# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# Copyright (C) 2004-2008 PC Solutions (<http://pcsol.be>). All Rights Reserved
from odoo import fields, models, api, _
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def _default_session(self):
        return self.env['cash.session'].search([('state', '=', 'opened'), ('user_id', '=', self.env.uid)], limit=1)

    session_id = fields.Many2one(
        'cash.session', string='Session', required=True, index=True,
        domain="[('state', '=', 'opened')]", states={'draft': [('readonly', False)]},
        readonly=True, default=_default_session)
    picking_id = fields.Many2one('stock.picking', string='Picking', readonly=True, copy=False)
    statement_ids = fields.One2many('account.bank.statement.line', 'cash_statement_id', string='Payments', states={
                                    'draft': [('readonly', False)]}, readonly=True)

    def _create_account_move(self, dt, ref, journal_id, company_id):
        date_tz_user = fields.Datetime.context_timestamp(self, fields.Datetime.from_string(dt))
        date_tz_user = fields.Date.to_string(date_tz_user)
        return self.env['account.move'].sudo().create({'ref': ref, 'journal_id': journal_id, 'date': date_tz_user})

    @api.multi
    def action_cash_order_done(self):
        return self._create_account_move_line()

    def _create_account_move_line(self, session=None, move=None):
        return True

    def _prepare_bank_statement_line_payment_values(self, data):
        """Create a new payment for the order"""
        args = {
            'amount': data['amount'],
            'date': data.get('payment_date', fields.Date.context_today(self)),
            'name': self.name + ': ' + (data.get('payment_name', '') or ''),
            'partner_id': self.env["res.partner"]._find_accounting_partner(self.partner_id).id or False,
        }

        journal_id = data.get('journal', False)
        statement_id = data.get('statement_id', False)
        assert journal_id or statement_id, "No statement_id or journal_id passed to the method!"

        journal = self.env['account.journal'].browse(journal_id)
        # use the company of the journal and not of the current user
        company_cxt = dict(self.env.context, force_company=journal.company_id.id)
        account_def = self.env['ir.property'].with_context(company_cxt).get(
            'property_account_receivable_id', 'res.partner')
        args['account_id'] = (self.partner_id.property_account_receivable_id.id) or (
            account_def and account_def.id) or False

        if not args['account_id']:
            if not args['partner_id']:
                msg = _('There is no receivable account defined to make payment.')
            else:
                msg = _('There is no receivable account defined to make payment for the partner: "%s" (id:%d).') % (
                    self.partner_id.name, self.partner_id.id,)
            raise UserError(msg)

        context = dict(self.env.context)
        context.pop('pos_session_id', False)
        for statement in self.session_id.statement_ids:
            if statement.id == statement_id:
                journal_id = statement.journal_id.id
                break
            elif statement.journal_id.id == journal_id:
                statement_id = statement.id
                break
        if not statement_id:
            raise UserError(_('You have to open at least one cashbox.'))

        args.update({
            'statement_id': statement_id,
            'cash_statement_id': self.id,
            'journal_id': journal_id,
            'ref': self.session_id.name,
        })

        return args

    def add_payment(self, data):
        """Create a new payment for the order"""
        self.ensure_one()
        args = self._prepare_bank_statement_line_payment_values(data)
        context = dict(self.env.context)
        context.pop('pos_session_id', False)
        self.env['account.bank.statement.line'].with_context(context).create(args)
        self.amount_paid = sum(payment.amount for payment in self.statement_ids)
        return args.get('statement_id', False)

    @api.multi
    def post(self):
        res = super(AccountPayment, self).post()
        data = {
            'amount':       self.amount or 0.0,
            'payment_date': self.payment_date,
            'statement_id': False,
            'payment_name': self.payment_reference,
            'journal':      self.journal_id.id,
        }
        self.add_payment(data)
        return res
