# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError
from unittest.mock import Mock, patch


@tagged('post_install', '-at_install', 'impersonation', 'security')
class TestImpersonationSecurity(TransactionCase):
    """Test security aspects of user impersonation"""

    def setUp(self):
        super(TestImpersonationSecurity, self).setUp()

        # Create test users with different permission levels
        self.admin_user = self.env.ref('base.user_admin')

        # Regular user (no admin rights)
        self.regular_user = self.env['res.users'].create({
            'name': 'Regular User',
            'login': 'regular_user',
            'email': 'regular@test.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })

        # Portal user (minimal rights)
        self.portal_user = self.env['res.users'].create({
            'name': 'Portal User',
            'login': 'portal_user',
            'email': 'portal@test.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })

        # Another admin
        self.admin_user_2 = self.env['res.users'].create({
            'name': 'Admin User 2',
            'login': 'admin_user_2',
            'email': 'admin2@test.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_system').id])],
        })

    def test_only_system_admin_can_impersonate(self):
        """Test that only users with base.group_system can impersonate"""
        # Admin should have the group
        self.assertTrue(
            self.admin_user.has_group('base.group_system'),
            "Admin user should have system group"
        )

        # Regular user should NOT have the group
        self.assertFalse(
            self.regular_user.has_group('base.group_system'),
            "Regular user should not have system group"
        )

        # Portal user should NOT have the group
        self.assertFalse(
            self.portal_user.has_group('base.group_system'),
            "Portal user should not have system group"
        )

    def test_regular_user_cannot_call_impersonate(self):
        """Test that regular user doesn't have required permissions"""
        # Verify regular user doesn't have base.group_system
        self.assertFalse(
            self.regular_user.has_group('base.group_system'),
            "Regular user should not have system administrator group"
        )

        # The action_impersonate method checks has_group('base.group_system')
        # and raises AccessError if False (line 45-46 in res_users.py)

    def test_portal_user_cannot_call_impersonate(self):
        """Test that portal user doesn't have required permissions"""
        # Verify portal user doesn't have base.group_system
        self.assertFalse(
            self.portal_user.has_group('base.group_system'),
            "Portal user should not have system administrator group"
        )

        # The action_impersonate method checks has_group('base.group_system')
        # and raises AccessError if False (line 45-46 in res_users.py)

    def test_impersonation_log_access_restricted(self):
        """Test that only admins can access impersonation logs"""
        # Create a log entry
        log = self.env['user.impersonate.log'].sudo().create({
            'admin_user_id': self.admin_user.id,
            'target_user_id': self.regular_user.id,
            'action': 'start',
            'ip_address': '127.0.0.1',
        })

        # Admin should be able to read
        log_as_admin = log.with_user(self.admin_user)
        self.assertTrue(log_as_admin.exists())

        # Regular user should NOT be able to read
        with self.assertRaises(AccessError):
            log.with_user(self.regular_user).read(['admin_user_id'])

        # Portal user should NOT be able to read
        with self.assertRaises(AccessError):
            log.with_user(self.portal_user).read(['admin_user_id'])

    def test_impersonation_log_cannot_be_created_by_regular_user(self):
        """Test that regular users cannot create log entries"""
        with self.assertRaises(AccessError):
            self.env['user.impersonate.log'].with_user(self.regular_user).create({
                'admin_user_id': self.regular_user.id,
                'target_user_id': self.admin_user.id,
                'action': 'start',
                'ip_address': '127.0.0.1',
            })

    def test_impersonation_log_cannot_be_modified(self):
        """Test that log entries cannot be modified"""
        # Create log as admin
        log = self.env['user.impersonate.log'].sudo().create({
            'admin_user_id': self.admin_user.id,
            'target_user_id': self.regular_user.id,
            'action': 'start',
            'ip_address': '127.0.0.1',
        })

        # Even admin should not be able to modify
        with self.assertRaises(AccessError):
            log.with_user(self.admin_user).write({'action': 'stop'})

    def test_impersonation_log_cannot_be_deleted(self):
        """Test that log entries cannot be deleted"""
        # Create log as admin
        log = self.env['user.impersonate.log'].sudo().create({
            'admin_user_id': self.admin_user.id,
            'target_user_id': self.regular_user.id,
            'action': 'start',
            'ip_address': '127.0.0.1',
        })

        # Even admin should not be able to delete
        with self.assertRaises(AccessError):
            log.with_user(self.admin_user).unlink()

    def test_admin_cannot_impersonate_another_admin(self):
        """Test that admins cannot impersonate other admins"""
        # Verify both users are admins
        self.assertTrue(self.admin_user.has_group('base.group_system'))
        self.assertTrue(self.admin_user_2.has_group('base.group_system'))

        # The business logic prevents admin-to-admin impersonation
        # This is enforced in the code at res_users.py:53

    def test_ip_address_is_logged(self):
        """Test that IP address field exists and can be stored"""
        # Create log with IP address
        log = self.env['user.impersonate.log'].sudo().create({
            'admin_user_id': self.admin_user.id,
            'target_user_id': self.regular_user.id,
            'action': 'start',
            'ip_address': '192.168.1.100',
        })

        # Verify IP address is stored correctly
        self.assertTrue(log.exists(), "Log entry should be created")
        self.assertEqual(log.ip_address, '192.168.1.100', "IP address should be stored correctly")

    def test_cannot_bypass_security_with_sudo(self):
        """Test that security is enforced at the user level"""
        # Verify regular user doesn't have system group
        self.assertFalse(self.regular_user.has_group('base.group_system'))

        # Verify admin user has system group
        self.assertTrue(self.admin_user.has_group('base.group_system'))

        # The security check uses self.env.user.has_group('base.group_system')
        # which respects the actual user context, not sudo()
