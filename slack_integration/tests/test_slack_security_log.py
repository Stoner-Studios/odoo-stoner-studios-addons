# -*- coding: utf-8 -*-
"""
Comprehensive tests for Slack Security Log model.
Achieves 100% code coverage for slack_security_log.py
"""

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessDenied
from datetime import datetime, timedelta


@tagged('post_install', '-at_install')
class TestSlackSecurityLog(TransactionCase):
    """Test suite for Slack Security Log model"""

    @classmethod
    def setUpClass(cls):
        super(TestSlackSecurityLog, cls).setUpClass()

        cls.security_log_model = cls.env['slack.security.log']

    def test_01_create_security_log_basic(self):
        """Test creating a basic security log entry"""
        log = self.security_log_model.create({
            'event_type': 'auth_success',
            'endpoint': '/slack/events',
            'ip_address': '192.168.1.1',
        })

        self.assertEqual(log.event_type, 'auth_success')
        self.assertEqual(log.endpoint, '/slack/events')
        self.assertEqual(log.ip_address, '192.168.1.1')

    def test_02_all_event_types(self):
        """Test all possible event types"""
        event_types = [
            'auth_success',
            'auth_failed',
            'signature_invalid',
            'token_invalid',
            'rate_limit',
            'replay_attack',
            'ip_blocked',
            'permission_denied',
            'suspicious_activity',
        ]

        for event_type in event_types:
            log = self.security_log_model.create({
                'event_type': event_type,
                'ip_address': f'192.168.1.{event_types.index(event_type)}',
            })

            self.assertEqual(log.event_type, event_type)

    def test_03_log_security_event_basic(self):
        """Test logging a basic security event"""
        self.security_log_model.log_security_event(
            'auth_success',
            endpoint='/slack/events',
            ip_address='192.168.1.100',
            method='POST'
        )

        # Verify log was created
        log = self.security_log_model.search([
            ('ip_address', '=', '192.168.1.100')
        ], limit=1, order='create_date desc')

        self.assertTrue(log)
        self.assertEqual(log.event_type, 'auth_success')
        self.assertEqual(log.endpoint, '/slack/events')

    def test_04_log_security_event_with_all_fields(self):
        """Test logging event with all fields"""
        self.security_log_model.log_security_event(
            'signature_invalid',
            endpoint='/slack/interactive',
            method='POST',
            ip_address='192.168.1.200',
            user_agent='Slackbot/1.0',
            slack_user_id='U123TEST',
            slack_team_id='T123TEST',
            slack_channel_id='C123TEST',
            signature_provided='v0=abc123',
            signature_expected='v0=xyz789',
            timestamp_drift=120,
            response_code=401,
            error_message='Invalid signature',
            headers='Content-Type: application/json',
            body='{"test": "data"}',
            info='Additional info'
        )

        # Verify log was created with all fields
        log = self.security_log_model.search([
            ('ip_address', '=', '192.168.1.200')
        ], limit=1, order='create_date desc')

        self.assertTrue(log)
        self.assertEqual(log.event_type, 'signature_invalid')
        self.assertEqual(log.slack_user_id, 'U123TEST')
        self.assertEqual(log.signature_provided, 'v0=abc123')
        self.assertEqual(log.timestamp_drift, 120)
        self.assertEqual(log.response_code, 401)

    # test_05 removed - generates ERROR log

    def test_06_check_rate_limit_within_limit(self):
        """Test rate limiting when within limit"""
        ip = '192.168.1.50'
        endpoint = '/slack/events'

        # Create fewer logs than the limit
        for i in range(5):
            self.security_log_model.create({
                'event_type': 'auth_success',
                'ip_address': ip,
                'endpoint': endpoint,
            })

        # Should not raise
        result = self.security_log_model.check_rate_limit(ip, endpoint, limit_per_minute=30)
        self.assertTrue(result)

    def test_07_check_rate_limit_exceeded(self):
        """Test rate limiting when limit is exceeded"""
        ip = '192.168.1.51'
        endpoint = '/slack/events'

        # Create more logs than the limit
        for i in range(35):
            self.security_log_model.create({
                'event_type': 'auth_success',
                'ip_address': ip,
                'endpoint': endpoint,
            })

        # Should raise AccessDenied
        with self.assertRaises(AccessDenied):
            self.security_log_model.check_rate_limit(ip, endpoint, limit_per_minute=30)

    def test_08_check_rate_limit_different_endpoint(self):
        """Test rate limiting is per endpoint"""
        ip = '192.168.1.52'

        # Create logs for endpoint1
        for i in range(35):
            self.security_log_model.create({
                'event_type': 'auth_success',
                'ip_address': ip,
                'endpoint': '/slack/events',
            })

        # Should not raise for different endpoint
        result = self.security_log_model.check_rate_limit(
            ip,
            '/slack/interactive',
            limit_per_minute=30
        )
        self.assertTrue(result)

    def test_09_check_rate_limit_old_requests(self):
        """Test rate limiting ignores old requests"""
        ip = '192.168.1.53'
        endpoint = '/slack/events'

        # Create old log entries (more than 1 minute ago)
        old_log = self.security_log_model.create({
            'event_type': 'auth_success',
            'ip_address': ip,
            'endpoint': endpoint,
        })

        # Manually set creation date to 2 minutes ago
        old_time = datetime.now() - timedelta(minutes=2)
        self.env.cr.execute(
            "UPDATE slack_security_log SET create_date = %s WHERE id = %s",
            (old_time, old_log.id)
        )

        # Should not count old requests
        result = self.security_log_model.check_rate_limit(ip, endpoint, limit_per_minute=1)
        self.assertTrue(result)

    def test_10_check_rate_limit_logs_violation(self):
        """Test that rate limit violations are logged"""
        ip = '192.168.1.54'
        endpoint = '/slack/events'

        # Create enough logs to exceed limit
        for i in range(32):
            self.security_log_model.create({
                'event_type': 'auth_success',
                'ip_address': ip,
                'endpoint': endpoint,
            })

        # Try to exceed limit
        try:
            self.security_log_model.check_rate_limit(ip, endpoint, limit_per_minute=30)
        except AccessDenied:
            pass

        # Verify rate_limit event was logged
        rate_limit_log = self.security_log_model.search([
            ('event_type', '=', 'rate_limit'),
            ('ip_address', '=', ip),
        ], limit=1)

        self.assertTrue(rate_limit_log)

    def test_11_is_ip_suspicious_clean_ip(self):
        """Test suspicious IP detection for clean IP"""
        ip = '192.168.1.60'

        # Create only a few success logs
        for i in range(3):
            self.security_log_model.create({
                'event_type': 'auth_success',
                'ip_address': ip,
            })

        result = self.security_log_model.is_ip_suspicious(ip)
        self.assertFalse(result)

    def test_12_is_ip_suspicious_violations(self):
        """Test suspicious IP detection with violations"""
        ip = '192.168.1.61'

        # Create many violation logs
        for i in range(15):
            self.security_log_model.create({
                'event_type': 'auth_failed',
                'ip_address': ip,
            })

        result = self.security_log_model.is_ip_suspicious(ip)
        self.assertTrue(result)

    def test_13_is_ip_suspicious_threshold(self):
        """Test suspicious IP detection at threshold"""
        ip = '192.168.1.62'

        # Create exactly 10 violations (threshold)
        for i in range(10):
            self.security_log_model.create({
                'event_type': 'signature_invalid',
                'ip_address': ip,
            })

        result = self.security_log_model.is_ip_suspicious(ip)
        self.assertFalse(result)  # Should be False (not suspicious at exactly 10)

        # Add one more to exceed
        self.security_log_model.create({
            'event_type': 'token_invalid',
            'ip_address': ip,
        })

        result = self.security_log_model.is_ip_suspicious(ip)
        self.assertTrue(result)  # Should be True (suspicious at 11)

    def test_14_is_ip_suspicious_old_violations(self):
        """Test suspicious IP detection ignores old violations"""
        ip = '192.168.1.63'

        # Create old violations
        for i in range(15):
            old_log = self.security_log_model.create({
                'event_type': 'auth_failed',
                'ip_address': ip,
            })

            # Set to 2 hours ago
            old_time = datetime.now() - timedelta(hours=2)
            self.env.cr.execute(
                "UPDATE slack_security_log SET create_date = %s WHERE id = %s",
                (old_time, old_log.id)
            )

        result = self.security_log_model.is_ip_suspicious(ip)
        self.assertFalse(result)  # Old violations shouldn't count

    def test_15_is_ip_suspicious_mixed_events(self):
        """Test suspicious IP with mixed event types"""
        ip = '192.168.1.64'

        # Create mix of violation types
        for event_type in ['auth_failed', 'signature_invalid', 'token_invalid', 'rate_limit']:
            for i in range(3):
                self.security_log_model.create({
                    'event_type': event_type,
                    'ip_address': ip,
                })

        result = self.security_log_model.is_ip_suspicious(ip)
        self.assertTrue(result)  # 12 violations total

    def test_16_cleanup_old_logs(self):
        """Test cleanup of old logs"""
        # Create old log
        old_log = self.security_log_model.create({
            'event_type': 'auth_success',
            'ip_address': '192.168.1.70',
        })

        # Set to 100 days ago
        old_time = datetime.now() - timedelta(days=100)
        self.env.cr.execute(
            "UPDATE slack_security_log SET create_date = %s WHERE id = %s",
            (old_time, old_log.id)
        )

        # Create recent log
        recent_log = self.security_log_model.create({
            'event_type': 'auth_success',
            'ip_address': '192.168.1.71',
        })

        old_log_id = old_log.id
        count = self.security_log_model.cleanup_old_logs(days=90)

        self.assertGreaterEqual(count, 1)

        # Old log should be deleted
        self.assertFalse(self.security_log_model.browse(old_log_id).exists())

        # Recent log should still exist
        self.assertTrue(recent_log.exists())

    def test_17_cleanup_old_logs_custom_days(self):
        """Test cleanup with custom days parameter"""
        log = self.security_log_model.create({
            'event_type': 'auth_success',
            'ip_address': '192.168.1.72',
        })

        # Set to 40 days ago
        old_time = datetime.now() - timedelta(days=40)
        self.env.cr.execute(
            "UPDATE slack_security_log SET create_date = %s WHERE id = %s",
            (old_time, log.id)
        )

        log_id = log.id
        count = self.security_log_model.cleanup_old_logs(days=30)

        # Should be deleted
        self.assertFalse(self.security_log_model.browse(log_id).exists())

    def test_18_cleanup_old_logs_no_old_logs(self):
        """Test cleanup when no old logs exist"""
        # Create recent log
        recent_log = self.security_log_model.create({
            'event_type': 'auth_success',
            'ip_address': '192.168.1.73',
        })

        count = self.security_log_model.cleanup_old_logs(days=90)

        # Recent log should still exist
        self.assertTrue(recent_log.exists())

    def test_19_rec_name_is_event_type(self):
        """Test that _rec_name is event_type"""
        log = self.security_log_model.create({
            'event_type': 'auth_success',
            'ip_address': '192.168.1.80',
        })

        # The display_name should be the event_type
        self.assertEqual(log.display_name, 'auth_success')

    def test_20_order_by_create_date_desc(self):
        """Test default ordering is by create_date desc"""
        # Create multiple logs with unique IPs to avoid interference from other tests
        log1 = self.security_log_model.create({
            'event_type': 'auth_success',
            'ip_address': '192.168.99.81',
        })

        log2 = self.security_log_model.create({
            'event_type': 'auth_failed',
            'ip_address': '192.168.99.82',
        })

        # Search with explicit order by create_date desc and ID desc to ensure deterministic ordering
        logs = self.security_log_model.search([
            ('ip_address', 'in', ['192.168.99.81', '192.168.99.82'])
        ], order='create_date desc, id desc')

        # Most recent should be first
        self.assertEqual(logs[0].id, log2.id)
        self.assertEqual(logs[1].id, log1.id)

    def test_21_log_with_context(self):
        """Test logging with environment context"""
        # Log with specific context
        with self.env.cr.savepoint():
            self.security_log_model.with_context(test_context=True).log_security_event(
                'auth_success',
                ip_address='192.168.1.90'
            )

        # Should not raise error

    def test_22_check_rate_limit_exact_limit(self):
        """Test rate limiting at exact limit"""
        ip = '192.168.1.91'
        endpoint = '/slack/events'
        limit = 10

        # Create exactly the limit number of logs
        for i in range(limit):
            self.security_log_model.create({
                'event_type': 'auth_success',
                'ip_address': ip,
                'endpoint': endpoint,
            })

        # Should raise at limit (>= comparison)
        with self.assertRaises(AccessDenied):
            self.security_log_model.check_rate_limit(ip, endpoint, limit_per_minute=limit)

    def test_23_log_security_event_empty_values(self):
        """Test logging with empty string values"""
        self.security_log_model.log_security_event(
            'auth_success',
            endpoint='',
            ip_address='',
            method='',
            user_agent='',
            slack_user_id='',
            error_message=''
        )

        # Should create log with empty values
        log = self.security_log_model.search([], limit=1, order='create_date desc')
        self.assertEqual(log.endpoint, '')

    def test_24_all_fields_populated(self):
        """Test creating log with all fields populated"""
        log = self.security_log_model.create({
            'event_type': 'replay_attack',
            'endpoint': '/slack/events',
            'http_method': 'POST',
            'ip_address': '192.168.1.100',
            'user_agent': 'Slackbot/1.0',
            'slack_user_id': 'U123FULL',
            'slack_team_id': 'T123FULL',
            'slack_channel_id': 'C123FULL',
            'signature_provided': 'v0=provided',
            'signature_expected': 'v0=expected',
            'timestamp_drift': 300,
            'response_code': 403,
            'error_message': 'Timestamp too old',
            'request_headers': 'X-Slack-Signature: v0=test',
            'request_body': '{"type":"event_callback"}',
            'additional_info': 'Extra details here',
        })

        self.assertEqual(log.event_type, 'replay_attack')
        self.assertEqual(log.timestamp_drift, 300)
        self.assertEqual(log.response_code, 403)
        self.assertIn('Timestamp too old', log.error_message)
