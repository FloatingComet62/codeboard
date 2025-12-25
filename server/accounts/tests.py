from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from leaderboard.models import Leetcode
from .models import User

CLAIMS = {
    'sub': '1234567890',
    'email': 'student@thapar.edu',
    'email_verified': True,
    'given_name': 'Test',
    'family_name': 'Student',
    'picture': 'https://example.com/a.png',
    'hd': 'thapar.edu',
}


@override_settings(GOOGLE_CLIENT_ID='client-id', GOOGLE_ALLOWED_DOMAINS=[])
class GoogleLoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def login(self, claims=CLAIMS):
        with mock.patch('accounts.views.id_token.verify_oauth2_token', return_value=claims) as verify:
            res = self.client.post('/api/auth/google/', {'credential': 'tok'}, format='json')
        return res, verify

    def test_creates_user_and_returns_token(self):
        res, verify = self.login()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(verify.call_args.args[2], 'client-id')
        self.assertFalse(res.data['user']['has_leetcode'])
        user = User.objects.get(email='student@thapar.edu')
        self.assertEqual(user.google_id, '1234567890')
        self.assertFalse(user.has_usable_password())

    def test_second_login_reuses_user_and_token(self):
        first, _ = self.login()
        second, _ = self.login()
        self.assertEqual(first.data['token'], second.data['token'])
        self.assertEqual(User.objects.count(), 1)

    def test_links_existing_email_account(self):
        User.objects.create_superuser('student@thapar.edu', 'pw')
        res, _ = self.login()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(User.objects.get().google_id, '1234567890')

    def test_rejects_invalid_token(self):
        with mock.patch('accounts.views.id_token.verify_oauth2_token', side_effect=ValueError):
            res = self.client.post('/api/auth/google/', {'credential': 'bad'}, format='json')
        self.assertEqual(res.status_code, 401)

    def test_rejects_unverified_email(self):
        res, _ = self.login({**CLAIMS, 'email_verified': False})
        self.assertEqual(res.status_code, 401)

    def test_missing_credential(self):
        res = self.client.post('/api/auth/google/', {}, format='json')
        self.assertEqual(res.status_code, 400)

    @override_settings(GOOGLE_ALLOWED_DOMAINS=['thapar.edu'])
    def test_domain_restriction(self):
        res, _ = self.login({**CLAIMS, 'email': 'x@gmail.com', 'sub': '9'} | {'hd': None})
        self.assertEqual(res.status_code, 401)
        res, _ = self.login()
        self.assertEqual(res.status_code, 200)

    def test_me_and_logout(self):
        res, _ = self.login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {res.data['token']}")
        self.assertEqual(self.client.get('/api/auth/me/').data['email'], 'student@thapar.edu')
        self.assertEqual(self.client.post('/api/auth/logout/').status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)


@mock.patch('leaderboard.views.get_user_data')
class LinkLeetcodeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('a@thapar.edu')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_profile_404_until_linked(self, get_user_data):
        res = self.client.get('/api/leaderboard/user/profile/')
        self.assertEqual(res.status_code, 404)
        self.assertIs(res.data['leetcode'], False)

        res = self.client.post('/api/leaderboard/register/', {'username': 'lc_user'}, format='json')
        self.assertEqual(res.status_code, 201)
        get_user_data.assert_called_once()
        self.assertEqual(self.client.get('/api/leaderboard/user/profile/').status_code, 200)
        self.assertTrue(self.client.get('/api/auth/me/').data['has_leetcode'])

    def test_cannot_link_twice(self, get_user_data):
        self.client.post('/api/leaderboard/register/', {'username': 'lc_user'}, format='json')
        res = self.client.post('/api/leaderboard/register/', {'username': 'other'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_cannot_take_someone_elses_account(self, get_user_data):
        other = User.objects.create_user('b@thapar.edu')
        Leetcode.objects.create(username='lc_user', user=other)
        res = self.client.post('/api/leaderboard/register/', {'username': 'LC_USER'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_claims_unlinked_account(self, get_user_data):
        acc = Leetcode.objects.create(username='lc_user')
        res = self.client.post('/api/leaderboard/register/', {'username': 'lc_user'}, format='json')
        self.assertEqual(res.status_code, 201)
        acc.refresh_from_db()
        self.assertEqual(acc.user, self.user)
