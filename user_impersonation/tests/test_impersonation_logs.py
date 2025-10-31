# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from unittest.mock import Mock, patch
import time


@tagged('post_install', '-at_install', 'impersonation', 'logs')
class TestImpersonationLogs(TransactionCase):
    """Test audit logging functionality"""

    def setUp(self):
        super(TestImpersonationLogs, self).setUp()

        self.admin_user = self.env.ref('base.user_admin')

        self.regular_user = self.env['res.users'].create({
            'name': 'Test User',
            'login': 'test_user',
            'email': 'test@test.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })

        # Mock request
        self.mock_request = Mock()
        self.mock_request.session = {
            'uid': self.admin_user.id,
            'impersonate_attempts': 0,
            'impersonate_last_attempt': 0,
        }
        self.mock_request.httprequest = Mock()
        self.mock_request.httprequest.environ = {'REMOTE_ADDR': '127.0.0.1'}
        self.mock_request.env = self.env
        self.mock_request.env.registry.clear_cache = Mock()

    def test_log_created_on_start(self):
        """Test that log entry can be created with start action"""
        # Count logs before
        logs_before = self.env['user.impersonate.log'].sudo().search_count([])

        # Create log manually (simulating what action_impersonate does)
        log = self.env['user.impersonate.log'].sudo().create({
            'admin_user_id': self.admin_user.id,
            'target_user_id': self.regular_user.id,
            'action': 'start',
            'ip_address': '127.0.0.1',
        })

        # Count logs after
        logs_after = self.env['user.impersonate.log'].sudo().search_count([])

        # Should have created one log
        self.assertEqual(logs_after, logs_before + 1, "Log entry should be created")

        # Verify log content
        self.assertTrue(log.exists())
        self.assertEqual(log.admin_user_id.id, self.admin_user.id)
        self.assertEqual(log.target_user_id.id, self.regular_user.id)
        self.assertEqual(log.action, 'start')
        self.assertEqual(log.ip_address, '127.0.0.1')

    def test_log_created_on_stop(self):
        """Test that log entry can be created with stop action"""
        # Count logs before
        logs_before = self.env['user.impersonate.log'].sudo().search_count([])

        # Create log manually (simulating what action_stop_impersonate does)
        log = self.env['user.impersonate.log'].sudo().create({
            'admin_user_id': self.admin_user.id,
            'target_user_id': self.regular_user.id,
            'action': 'stop',
            'ip_address': '127.0.0.1',
        })

        # Count logs after
        logs_after = self.env['user.impersonate.log'].sudo().search_count([])

        # Should have created one log
        self.assertEqual(logs_after, logs_before + 1, "Stop log entry should be created")

        # Verify log content
        self.assertTrue(log.exists())
        self.assertEqual(log.action, 'stop')

    def test_complete_session_creates_two_logs(self):
        """Test that complete impersonation session creates start and stop logs"""
        # Count initial logs
        initial_count = self.env['user.impersonate.log'].sudo().search_count([
            ('admin_user_id', '=', self.admin_user.id),
            ('target_user_id', '=', self.regular_user.id),
        ])

        # Create start log
        self.env['user.impersonate.log'].sudo().create({
            'admin_user_id': self.admin_user.id,
            'target_user_id': self.regular_user.id,
            'action': 'start',
            'ip_address': '127.0.0.1',
        })

        # Create stop log
        self.env['user.impersonate.log'].sudo().create({
            'admin_user_id': self.admin_user.id,
            'target_user_id': self.regular_user.id,
            'action': 'stop',
            'ip_address': '127.0.0.1',
        })

        # Count final logs
        final_count = self.env['user.impersonate.log'].sudo().search_count([
            ('admin_user_id', '=', self.admin_user.id),
            ('target_user_id', '=', self.regular_user.id),
        ])

        # Should have two new logs (start + stop)
        self.assertEqual(final_count, initial_count + 2, "Should have start and stop logs")

    def test_log_duration_computed(self):
        """Test that log duration field exists and is computed"""
        # Create stop log
        stop_log = self.env['user.impersonate.log'].sudo().create({
            'admin_user_id': self.admin_user.id,
            'target_user_id': self.regular_user.id,
            'action': 'stop',
            'ip_address': '127.0.0.1',
        })

        # Verify duration field exists and is numeric
        self.assertIsNotNone(stop_log.duration, "Duration field should exist")
        self.assertIsInstance(stop_log.duration, (int, float), "Duration should be numeric")

    def test_log_duration_zero_for_start(self):
        """Test that duration is 0 for start actions"""
        log = self.env['user.impersonate.log'].sudo().create({
            'admin_user_id': self.admin_user.id,
            'target_user_id': self.regular_user.id,
            'action': 'start',
            'ip_address': '127.0.0.1',
        })

        self.assertEqual(log.duration, 0.0, "Duration should be 0 for start action")

    def test_logs_are_searchable_by_admin(self):
        """Test that logs can be searched and filtered by admin"""
        # Count existing logs first
        existing_logs = self.env['user.impersonate.log'].sudo().search_count([
            ('admin_user_id', '=', self.admin_user.id),
            ('target_user_id', '=', self.regular_user.id),
        ])

        # Create multiple logs
        for i in range(5):
            self.env['user.impersonate.log'].sudo().create({
                'admin_user_id': self.admin_user.id,
                'target_user_id': self.regular_user.id,
                'action': 'start' if i % 2 == 0 else 'stop',
                'ip_address': f'127.0.0.{i}',
            })

        # Search by admin and target
        logs = self.env['user.impersonate.log'].sudo().search([
            ('admin_user_id', '=', self.admin_user.id),
            ('target_user_id', '=', self.regular_user.id),
        ])
        self.assertEqual(len(logs), existing_logs + 5)

        # Search by action (filter by our test users to avoid counting other tests' logs)
        start_logs = self.env['user.impersonate.log'].sudo().search([
            ('admin_user_id', '=', self.admin_user.id),
            ('target_user_id', '=', self.regular_user.id),
            ('action', '=', 'start'),
        ])
        self.assertEqual(len(start_logs), 3)

        stop_logs = self.env['user.impersonate.log'].sudo().search([
            ('admin_user_id', '=', self.admin_user.id),
            ('target_user_id', '=', self.regular_user.id),
            ('action', '=', 'stop'),
        ])
        self.assertEqual(len(stop_logs), 2)

    def test_logs_ordered_by_date(self):
        """Test that logs are ordered by date (most recent first)"""
        # Create logs with different dates
        old_log = self.env['user.impersonate.log'].sudo().create({
            'admin_user_id': self.admin_user.id,
            'target_user_id': self.regular_user.id,
            'action': 'start',
            'ip_address': '127.0.0.1',
            'create_date': '2025-01-01 10:00:00',
        })

        new_log = self.env['user.impersonate.log'].sudo().create({
            'admin_user_id': self.admin_user.id,
            'target_user_id': self.regular_user.id,
            'action': 'start',
            'ip_address': '127.0.0.2',
            'create_date': '2025-01-02 10:00:00',
        })

        # Search logs
        logs = self.env['user.impersonate.log'].sudo().search([
            ('admin_user_id', '=', self.admin_user.id),
        ], order='create_date desc')

        # Most recent should be first
        self.assertEqual(logs[0].id, new_log.id, "Most recent log should be first")
        self.assertEqual(logs[1].id, old_log.id, "Older log should be second")

    def test_log_contains_all_required_fields(self):
        """Test that log entry contains all required fields"""
        log = self.env['user.impersonate.log'].sudo().create({
            'admin_user_id': self.admin_user.id,
            'target_user_id': self.regular_user.id,
            'action': 'start',
            'ip_address': '192.168.1.1',
        })

        # Verify all fields are set
        self.assertTrue(log.admin_user_id.exists())
        self.assertTrue(log.target_user_id.exists())
        self.assertIn(log.action, ['start', 'stop'])
        self.assertTrue(log.ip_address)
        self.assertTrue(log.create_date)

    def test_different_ips_are_logged(self):
        """Test that different IP addresses are correctly logged"""
        ips = ['127.0.0.1', '192.168.1.1', '10.0.0.1', '172.16.0.1']

        for ip in ips:
            log = self.env['user.impersonate.log'].sudo().create({
                'admin_user_id': self.admin_user.id,
                'target_user_id': self.regular_user.id,
                'action': 'start',
                'ip_address': ip,
            })
            self.assertEqual(log.ip_address, ip, f"IP {ip} should be logged correctly")

    def test_log_survives_session_cleanup(self):
        """Test that logs persist in database"""
        # Create log
        log = self.env['user.impersonate.log'].sudo().create({
            'admin_user_id': self.admin_user.id,
            'target_user_id': self.regular_user.id,
            'action': 'start',
            'ip_address': '127.0.0.1',
        })

        log_id = log.id

        # Verify log exists
        self.assertTrue(log.exists(), "Log should exist after creation")

        # Search for log again
        log_after = self.env['user.impersonate.log'].sudo().browse(log_id)
        self.assertTrue(log_after.exists(), "Log should persist in database")
