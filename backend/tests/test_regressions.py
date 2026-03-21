import importlib
import os
import sys
import unittest
from datetime import date, timedelta


os.environ.setdefault('DATABASE_URL', 'sqlite+pysqlite:///:memory:')
os.environ.setdefault('JWT_SECRET_KEY', '0123456789abcdef0123456789abcdef')
os.environ.setdefault('JWT_REFRESH_SECRET_KEY', 'fedcba9876543210fedcba9876543210')
os.environ.setdefault('DATA_ENCRYPTION_KEY', 'MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=')
os.environ.setdefault('ADMIN_BOOTSTRAP_EMAIL', 'admin@example.com')
os.environ.setdefault('ADMIN_BOOTSTRAP_PASSWORD', 'supersecurepw')


class BackendRegressionTests(unittest.TestCase):
    def test_main_module_imports_without_dependency_name_errors(self) -> None:
        sys.modules.pop('backend.app.main', None)
        module = importlib.import_module('backend.app.main')

        self.assertEqual(module.app.title, 'V2free Secure Backend')
        self.assertTrue(callable(module.get_current_user_optional))

    def test_content_access_requires_current_subscription_window(self) -> None:
        from backend.app.models import ContentVisibility, Plan, SecureContent, Subscription, SubscriptionStatus, User
        from backend.app.services import can_read_content, subscription_is_current, user_has_paid_access

        today = date(2026, 3, 21)
        premium_plan = Plan(code='premium', name='Premium', price_monthly=19, includes_premium_content=True)
        premium_content = SecureContent(
            slug='premium-story',
            title='Premium Story',
            summary='Premium summary',
            encrypted_body='ciphertext',
            visibility=ContentVisibility.PREMIUM,
            is_published=True,
        )
        subscriber_content = SecureContent(
            slug='subscriber-story',
            title='Subscriber Story',
            summary='Subscriber summary',
            encrypted_body='ciphertext',
            visibility=ContentVisibility.SUBSCRIBER,
            is_published=True,
        )

        scenarios = {
            'future subscription': Subscription(
                plan=premium_plan,
                status=SubscriptionStatus.ACTIVE,
                start_date=today + timedelta(days=1),
                end_date=today + timedelta(days=30),
            ),
            'expired subscription': Subscription(
                plan=premium_plan,
                status=SubscriptionStatus.ACTIVE,
                start_date=today - timedelta(days=30),
                end_date=today - timedelta(days=1),
            ),
            'current subscription': Subscription(
                plan=premium_plan,
                status=SubscriptionStatus.ACTIVE,
                start_date=today - timedelta(days=1),
                end_date=today + timedelta(days=30),
            ),
        }

        expected_currentness = {
            'future subscription': False,
            'expired subscription': False,
            'current subscription': True,
        }

        for label, subscription in scenarios.items():
            with self.subTest(label=label):
                user = User(
                    email=f'{label.replace(" ", "-")}@example.com',
                    full_name='Test User',
                    password_hash='hash',
                )
                user.subscriptions.append(subscription)

                self.assertEqual(subscription_is_current(subscription, today=today), expected_currentness[label])
                self.assertEqual(user_has_paid_access(user, today=today), expected_currentness[label])
                self.assertEqual(can_read_content(user, premium_content, today=today), expected_currentness[label])
                self.assertEqual(can_read_content(user, subscriber_content, today=today), expected_currentness[label])


if __name__ == '__main__':
    unittest.main()
