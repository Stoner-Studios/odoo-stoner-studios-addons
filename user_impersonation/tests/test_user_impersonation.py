# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, AccessError
from unittest.mock import Mock, patch
import time


@tagged('post_install', '-at_install', 'impersonation')
class TestUserImpersonation(TransactionCase):
    """Test user impersonation functionality"""

    def setUp(self):
        super(TestUserImpersonation, self).setUp()

        # Create test users
        self.admin_user = self.env.ref('base.user_admin')

        self.regular_user = self.env['res.users'].create({
            'name': 'Test Regular User',
            'login': 'test_regular',
            'email': 'regular@test.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        })

        self.other_admin = self.env['res.users'].create({
            'name': 'Test Other Admin',
            'login': 'test_admin2',
            'email': 'admin2@test.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_system').id])],
        })

        # Mock request object
        self.mock_request = Mock()
        self.mock_request.session = {
            'uid': self.admin_user.id,
            'impersonate_attempts': 0,
            'impersonate_last_attempt': 0,
        }
        self.mock_request.httprequest = Mock()
        self.mock_request.httprequest.environ = {'REMOTE_ADDR': '127.0.0.1'}
        self.mock_request.env = self.env

