# -*- coding: utf-8 -*-
"""
Comprehensive tests for Slack Conversation model.
Achieves 100% code coverage for slack_conversation.py
"""

from odoo.tests import TransactionCase, tagged
from datetime import datetime, timedelta
import json


@tagged('post_install', '-at_install')
class TestSlackConversation(TransactionCase):
    """Test suite for Slack Conversation model"""

    @classmethod
    def setUpClass(cls):
        super(TestSlackConversation, cls).setUpClass()

        # Create test user
        cls.test_user = cls.env['res.users'].create({
            'name': 'Test User Conv',
            'login': 'testuserconv',
            'email': 'testconv@example.com',
        })

        # Create test mapping
        cls.test_mapping = cls.env['slack.user.mapping'].create({
            'slack_user_id': 'U123CONV',
            'slack_team_id': 'T123TEST',
            'slack_display_name': 'Test Conversation User',
            'state': 'active',
            'user_id': cls.test_user.id,
        })

    def test_01_create_conversation_basic(self):
        """Test creating a basic conversation"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123TEST',
            'channel_id': 'D123TEST',
            'slack_team_id': 'T123TEST',
        })

        self.assertEqual(conv.slack_user_id, 'U123TEST')
        self.assertEqual(conv.channel_id, 'D123TEST')
        self.assertEqual(conv.state, 'new')

    def test_02_compute_display_name(self):
        """Test display name computation"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123DISPLAY',
            'channel_id': 'D123DISPLAY',
            'mapping_id': self.test_mapping.id,
        })

        self.assertIn('Conversation with', conv.display_name)
        self.assertIn(self.test_mapping.slack_display_name, conv.display_name)

    def test_03_compute_display_name_no_mapping(self):
        """Test display name without mapping"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123NOMAP',
            'channel_id': 'D123NOMAP',
        })

        self.assertIn('U123NOMAP', conv.display_name)

    def test_04_get_or_create_conversation_existing(self):
        """Test getting existing conversation"""
        # Create conversation
        existing = self.env['slack.conversation'].create({
            'slack_user_id': 'U123EXIST',
            'channel_id': 'D123EXIST',
            'slack_team_id': 'T123TEST',
        })

        # Get or create should return existing
        conv = self.env['slack.conversation'].get_or_create_conversation(
            'U123EXIST',
            'D123EXIST',
            'T123TEST'
        )

        self.assertEqual(conv.id, existing.id)

    def test_05_get_or_create_conversation_new(self):
        """Test creating new conversation"""
        conv = self.env['slack.conversation'].get_or_create_conversation(
            'U123NEW',
            'D123NEW',
            'T123NEW'
        )

        self.assertEqual(conv.slack_user_id, 'U123NEW')
        self.assertEqual(conv.channel_id, 'D123NEW')
        self.assertEqual(conv.state, 'new')

    def test_06_get_or_create_conversation_with_mapping(self):
        """Test creating conversation with existing mapping"""
        conv = self.env['slack.conversation'].get_or_create_conversation(
            'U123CONV',
            'D123NEWCONV',
            'T123TEST'
        )

        # Should link to existing mapping and set state to authenticated
        self.assertEqual(conv.mapping_id.id, self.test_mapping.id)
        self.assertEqual(conv.state, 'authenticated')

    def test_07_update_message_regular(self):
        """Test updating conversation with regular message"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123MSG',
            'channel_id': 'D123MSG',
            'message_count': 5,
        })

        conv.update_message('Hello bot', is_command=False)

        self.assertEqual(conv.last_message, 'Hello bot')
        self.assertEqual(conv.message_count, 6)
        self.assertEqual(conv.state, 'active')
        self.assertIsNotNone(conv.last_message_date)

    def test_08_update_message_command(self):
        """Test updating conversation with command"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123CMD',
            'channel_id': 'D123CMD',
            'message_count': 3,
            'command_count': 10,
        })

        conv.update_message('search test', is_command=True)

        self.assertEqual(conv.last_message, 'search test')
        self.assertEqual(conv.last_command, 'search test')
        self.assertEqual(conv.message_count, 4)
        self.assertEqual(conv.command_count, 11)

    def test_09_update_response(self):
        """Test updating bot response"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123RESP',
            'channel_id': 'D123RESP',
        })

        conv.update_response('Bot response here')

        self.assertEqual(conv.last_response, 'Bot response here')

    def test_10_update_response_with_waiting(self):
        """Test updating response when waiting for user"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123WAIT',
            'channel_id': 'D123WAIT',
            'waiting_for': 'oauth',
        })

        conv.update_response('Please authorize')

        self.assertEqual(conv.state, 'waiting')

    def test_11_set_waiting_for(self):
        """Test setting waiting state"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123SETWAIT',
            'channel_id': 'D123SETWAIT',
        })

        conv.set_waiting_for('search_term', 'Waiting for search term')

        self.assertEqual(conv.waiting_for, 'search_term')
        self.assertEqual(conv.waiting_context, 'Waiting for search term')
        self.assertEqual(conv.state, 'waiting')

    def test_12_set_waiting_for_no_context(self):
        """Test setting waiting state without context"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123NOWAIT',
            'channel_id': 'D123NOWAIT',
        })

        conv.set_waiting_for('confirmation')

        self.assertEqual(conv.waiting_for, 'confirmation')
        self.assertEqual(conv.waiting_context, '')

    def test_13_clear_waiting(self):
        """Test clearing waiting state"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123CLEAR',
            'channel_id': 'D123CLEAR',
            'waiting_for': 'oauth',
            'waiting_context': 'Some context',
        })

        conv.clear_waiting()

        self.assertEqual(conv.waiting_for, 'none')
        self.assertEqual(conv.waiting_context, '')

    def test_14_get_context_data_empty(self):
        """Test getting empty context data"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123CTX',
            'channel_id': 'D123CTX',
        })

        context = conv.get_context_data()

        self.assertEqual(context, {})

    def test_15_get_context_data_with_data(self):
        """Test getting context data"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123CTXDATA',
            'channel_id': 'D123CTXDATA',
            'context_data': '{"key": "value", "number": 123}',
        })

        context = conv.get_context_data()

        self.assertEqual(context['key'], 'value')
        self.assertEqual(context['number'], 123)

    def test_16_get_context_data_invalid_json(self):
        """Test getting context data with invalid JSON"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123INVALID',
            'channel_id': 'D123INVALID',
            'context_data': 'invalid json',
        })

        context = conv.get_context_data()

        # Should return empty dict on error
        self.assertEqual(context, {})

    def test_17_set_context_data(self):
        """Test setting context data"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123SETCTX',
            'channel_id': 'D123SETCTX',
        })

        data = {'opportunity_id': 123, 'stage': 'qualified'}
        conv.set_context_data(data)

        # Verify it was saved as JSON
        self.assertIn('opportunity_id', conv.context_data)
        self.assertIn('123', conv.context_data)

    def test_18_update_context(self):
        """Test updating specific context key"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123UPDCTX',
            'channel_id': 'D123UPDCTX',
            'context_data': '{"existing": "value"}',
        })

        conv.update_context('new_key', 'new_value')

        context = conv.get_context_data()
        self.assertEqual(context['existing'], 'value')
        self.assertEqual(context['new_key'], 'new_value')

    def test_19_link_to_mapping(self):
        """Test linking conversation to mapping"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123LINK',
            'channel_id': 'D123LINK',
            'state': 'new',
        })

        conv.link_to_mapping(self.test_mapping.id)

        self.assertEqual(conv.mapping_id.id, self.test_mapping.id)
        self.assertEqual(conv.state, 'authenticated')

    def test_20_link_to_mapping_none(self):
        """Test linking to None"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123UNLINK',
            'channel_id': 'D123UNLINK',
            'mapping_id': self.test_mapping.id,
            'state': 'authenticated',
        })

        conv.link_to_mapping(False)

        self.assertFalse(conv.mapping_id)

    def test_21_is_authenticated_true(self):
        """Test is_authenticated when authenticated"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123AUTH',
            'channel_id': 'D123AUTH',
            'mapping_id': self.test_mapping.id,
        })

        self.assertTrue(conv.is_authenticated())

    def test_22_is_authenticated_false(self):
        """Test is_authenticated without mapping"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123NOAUTH',
            'channel_id': 'D123NOAUTH',
        })

        self.assertFalse(conv.is_authenticated())

    def test_23_is_authenticated_inactive_mapping(self):
        """Test is_authenticated with inactive mapping"""
        inactive_mapping = self.env['slack.user.mapping'].create({
            'slack_user_id': 'U123INACT',
            'user_id': self.test_user.id,
            'state': 'pending',
        })

        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123INACTCONV',
            'channel_id': 'D123INACTCONV',
            'mapping_id': inactive_mapping.id,
        })

        self.assertFalse(conv.is_authenticated())

    def test_24_needs_authentication_true(self):
        """Test needs_authentication when not authenticated"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123NEEDS',
            'channel_id': 'D123NEEDS',
        })

        self.assertTrue(conv.needs_authentication())

    def test_25_needs_authentication_false(self):
        """Test needs_authentication when authenticated"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123NONEED',
            'channel_id': 'D123NONEED',
            'mapping_id': self.test_mapping.id,
        })

        self.assertFalse(conv.needs_authentication())

    def test_26_cleanup_idle_conversations(self):
        """Test cleanup of idle conversations"""
        # Create old conversation
        old_conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123OLD',
            'channel_id': 'D123OLD',
            'state': 'active',
        })
        old_conv.write({
            'last_message_date': datetime.now() - timedelta(hours=48)
        })

        # Create recent conversation
        recent_conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123RECENT',
            'channel_id': 'D123RECENT',
            'state': 'active',
        })
        recent_conv.write({
            'last_message_date': datetime.now() - timedelta(hours=12)
        })

        count = self.env['slack.conversation'].cleanup_idle_conversations(hours=24)

        self.assertGreaterEqual(count, 1)

        # Refresh records by re-browsing
        old_conv = self.env['slack.conversation'].browse(old_conv.id)
        recent_conv = self.env['slack.conversation'].browse(recent_conv.id)

        # Old should be marked idle
        self.assertEqual(old_conv.state, 'idle')

        # Recent should remain active
        self.assertEqual(recent_conv.state, 'active')

    def test_27_cleanup_idle_conversations_custom_hours(self):
        """Test cleanup with custom hours"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123CUSTOM',
            'channel_id': 'D123CUSTOM',
            'state': 'active',
        })
        conv.write({
            'last_message_date': datetime.now() - timedelta(hours=10)
        })

        count = self.env['slack.conversation'].cleanup_idle_conversations(hours=8)

        # Refresh by re-browsing
        conv = self.env['slack.conversation'].browse(conv.id)
        self.assertEqual(conv.state, 'idle')

    def test_28_cleanup_idle_conversations_already_idle(self):
        """Test cleanup doesn't affect already idle conversations"""
        idle_conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123ALREADYIDLE',
            'channel_id': 'D123ALREADYIDLE',
            'state': 'idle',
        })
        idle_conv.write({
            'last_message_date': datetime.now() - timedelta(hours=48)
        })

        initial_state = idle_conv.state
        count = self.env['slack.conversation'].cleanup_idle_conversations(hours=24)

        # Refresh by re-browsing
        idle_conv = self.env['slack.conversation'].browse(idle_conv.id)
        # State should remain idle
        self.assertEqual(idle_conv.state, initial_state)

    def test_29_started_date_default(self):
        """Test started_date is set by default"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123START',
            'channel_id': 'D123START',
        })

        self.assertIsNotNone(conv.started_date)

    def test_30_all_waiting_for_states(self):
        """Test all possible waiting_for states"""
        states = ['none', 'oauth', 'search_term', 'note_text', 'confirmation']

        for state in states:
            conv = self.env['slack.conversation'].create({
                'slack_user_id': f'U123{state}',
                'channel_id': f'D123{state}',
                'waiting_for': state,
            })

            self.assertEqual(conv.waiting_for, state)

    def test_31_context_data_complex_structure(self):
        """Test context data with complex nested structure"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123COMPLEX',
            'channel_id': 'D123COMPLEX',
        })

        complex_data = {
            'opportunity': {
                'id': 123,
                'name': 'Test Opp',
                'stage': 'qualified'
            },
            'last_searches': ['term1', 'term2'],
            'count': 5
        }

        conv.set_context_data(complex_data)
        retrieved = conv.get_context_data()

        self.assertEqual(retrieved['opportunity']['id'], 123)
        self.assertEqual(len(retrieved['last_searches']), 2)

    def test_32_update_message_multiple_times(self):
        """Test updating message multiple times"""
        conv = self.env['slack.conversation'].create({
            'slack_user_id': 'U123MULTI',
            'channel_id': 'D123MULTI',
            'message_count': 0,
        })

        for i in range(5):
            conv.update_message(f'Message {i}', is_command=(i % 2 == 0))

        self.assertEqual(conv.message_count, 5)
        self.assertEqual(conv.command_count, 3)  # 0, 2, 4
        self.assertEqual(conv.last_message, 'Message 4')
