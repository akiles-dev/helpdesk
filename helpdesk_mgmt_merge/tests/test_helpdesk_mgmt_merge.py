from odoo.exceptions import AccessError
from odoo.tests import new_test_user

from odoo.addons.base.tests.common import BaseCommon


class TestHelpdeskTicketMerge(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.HelpdeskTicketMerge = cls.env["helpdesk.ticket.merge"]
        cls.ticket_1 = cls._create_ticket("Ticket 1", "Description for Ticket 1")
        cls.ticket_2 = cls._create_ticket("Ticket 2", "Description for Ticket 2")

    @classmethod
    def _create_ticket(cls, name, description):
        return cls.env["helpdesk.ticket"].create(
            {
                "name": name,
                "description": description,
            }
        )

    def test_helpdesk_ticket_merge_create_new_ticket(self):
        self.ticket_merge_1 = self.HelpdeskTicketMerge.with_context(
            active_ids=[self.ticket_1.id, self.ticket_2.id]
        ).create({"create_new_ticket": True, "dst_ticket_name": "Test 1"})
        self.ticket_merge_1.merge_tickets()
        self.assertEqual(self.ticket_merge_1.dst_ticket_id.name, "Test 1")

    def test_helpdesk_ticket_merge_with_existing_ticket(self):
        self.ticket_merge_2 = self.HelpdeskTicketMerge.with_context(
            active_ids=[self.ticket_1.id, self.ticket_2.id]
        ).create({})
        self.assertEqual(self.ticket_merge_2.user_id, self.env.user)
        self.ticket_2.user_id = self.env.user.id
        self.ticket_merge_2.dst_ticket_id = self.ticket_2.id
        self.ticket_merge_2._onchange_dst_ticket_id()
        self.assertTrue(self.ticket_merge_2.user_id)
        self.ticket_merge_2.merge_tickets()
        self.assertEqual(self.ticket_merge_2.dst_ticket_id.name, "Ticket 2")

    def test_helpdesk_ticket_merge_as_helpdesk_user(self):
        # A helpdesk user is not an admin, and Odoo allows only admins to
        # change res_id on mail.message. The merge must still move the
        # messages to the destination ticket.
        user = new_test_user(
            self.env,
            login="helpdesk_mgmt_merge-user",
            groups="helpdesk_mgmt.group_helpdesk_user",
        )
        message = self.ticket_1.message_post(
            body="Hello", message_type="comment"
        )
        wizard = (
            self.HelpdeskTicketMerge.with_user(user)
            .with_context(active_ids=[self.ticket_1.id, self.ticket_2.id])
            .create({})
        )
        wizard.dst_ticket_id = self.ticket_2.id
        wizard.merge_tickets()
        self.assertEqual(message.res_id, self.ticket_2.id)
        self.assertFalse(self.ticket_1.active)

    def test_helpdesk_ticket_merge_as_team_user(self):
        # A team user can merge the tickets of their own team.
        team = self.env["helpdesk.ticket.team"].create({"name": "Team A"})
        user = new_test_user(
            self.env,
            login="helpdesk_mgmt_merge-team",
            groups="helpdesk_mgmt.group_helpdesk_user_team",
        )
        team.user_ids = [(4, user.id)]
        (self.ticket_1 | self.ticket_2).team_id = team
        wizard = (
            self.HelpdeskTicketMerge.with_user(user)
            .with_context(active_ids=[self.ticket_1.id, self.ticket_2.id])
            .create({})
        )
        wizard.dst_ticket_id = self.ticket_2.id
        wizard.merge_tickets()
        self.assertFalse(self.ticket_1.active)

    def test_helpdesk_ticket_merge_as_team_user_other_team(self):
        # A team user cannot merge a ticket of another team.
        team_a = self.env["helpdesk.ticket.team"].create({"name": "Team A"})
        team_b = self.env["helpdesk.ticket.team"].create({"name": "Team B"})
        user = new_test_user(
            self.env,
            login="helpdesk_mgmt_merge-team",
            groups="helpdesk_mgmt.group_helpdesk_user_team",
        )
        team_a.user_ids = [(4, user.id)]
        self.ticket_1.team_id = team_b
        self.ticket_2.team_id = team_a
        with self.assertRaises(AccessError):
            wizard = (
                self.HelpdeskTicketMerge.with_user(user)
                .with_context(active_ids=[self.ticket_2.id])
                .create({"ticket_ids": [(6, 0, [self.ticket_1.id, self.ticket_2.id])]})
            )
            wizard.dst_ticket_id = self.ticket_2.id
            wizard.merge_tickets()
        self.assertTrue(self.ticket_1.active)
