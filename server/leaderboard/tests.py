from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from . import tasks
from .models import Leaderboard, Leetcode, Question

IST = ZoneInfo('Asia/Kolkata')
ALL_QUESTIONS = [
    {'frontendQuestionId': '1', 'titleSlug': 'two-sum'},
    {'frontendQuestionId': '2', 'titleSlug': 'add-two-numbers'},
]


def ts(dt):
    return int(dt.timestamp())


class FetchUserDataTests(TestCase):
    def setUp(self):
        tasks._all_questions_cache.update(fetched_at=0.0, questions=[])
        self.assigned_at = timezone.now() - timedelta(days=2)
        Question.objects.create(leetcode_id=1, title='Two Sum', titleSlug='two-sum', questionDate=self.assigned_at)
        Question.objects.create(leetcode_id=2, title='Add Two Numbers', titleSlug='add-two-numbers', questionDate=self.assigned_at)
        self.acc = Leetcode.objects.create(username='alice')

    def refresh(self, recent):
        def fake_query(query, variables):
            if query is tasks.MATCHED_USER_QUERY:
                return {'data': {'matchedUser': {'profile': {'realName': 'Alice', 'ranking': 5, 'userAvatar': 'a.png'}}}}
            if query is tasks.QUESTIONS_SUBMITTED_QUERY:
                return {'data': {'recentAcSubmissionList': recent}}
            if query is tasks.LANGUAGE_PROBLEM_COUNT_QUERY:
                return {'data': {'matchedUser': {'languageProblemCount': [{'problemsSolved': 3}]}}}
            return {'data': {'problemsetQuestionList': {'questions': ALL_QUESTIONS}}}
        with mock.patch.object(tasks, 'send_query', side_effect=fake_query) as send:
            tasks.get_user_data(self.acc.username, self.acc.pk)
        self.acc.refresh_from_db()
        return send

    def test_solves_from_earlier_refreshes_still_count(self):
        solved_1 = ts(timezone.now() - timedelta(hours=3))
        solved_2 = ts(timezone.now() - timedelta(hours=1))
        self.refresh([{'titleSlug': 'two-sum', 'timestamp': str(solved_1)}])
        # Two Sum has dropped out of LeetCode's recent list by the next refresh
        self.refresh([{'titleSlug': 'add-two-numbers', 'timestamp': str(solved_2)}])

        self.assertEqual(self.acc.total_solved_dict, {'1': solved_1, '2': solved_2})
        self.assertEqual(self.acc.matched_ques_dict, {'1': solved_1, '2': solved_2})
        self.assertEqual(self.acc.matched_ques, 2)

    def test_first_solve_time_is_kept(self):
        first = ts(timezone.now() - timedelta(hours=3))
        self.refresh([{'titleSlug': 'two-sum', 'timestamp': str(first)}])
        self.refresh([{'titleSlug': 'two-sum', 'timestamp': str(first + 600)}])
        self.assertEqual(self.acc.total_solved_dict, {'1': first})

    def test_solved_before_assignment_does_not_count(self):
        self.refresh([{'titleSlug': 'two-sum', 'timestamp': str(ts(self.assigned_at) - 60)}])
        self.assertEqual(self.acc.matched_ques, 0)

    def test_full_question_list_is_cached_between_users(self):
        first = self.refresh([])
        second = self.refresh([])
        fetched = [c for c in first.call_args_list + second.call_args_list if c.args[0] is tasks.ALL_QUESTION_LIST_QUERY]
        self.assertEqual(len(fetched), 1)


class AssignedQuestionTimestampTests(TestCase):
    def test_uses_real_epoch_regardless_of_server_timezone(self):
        when = datetime(2026, 1, 1, 0, 0, tzinfo=IST)
        Question.objects.create(leetcode_id=1, title='t', titleSlug='t', questionDate=when)
        self.assertEqual(tasks.get_assigned_questions()[0][2], when.timestamp())


class CalculateLeaderboardTests(TestCase):
    def setUp(self):
        assigned = timezone.now() - timedelta(days=3)
        for i in (1, 2):
            Question.objects.create(leetcode_id=i, title=str(i), titleSlug=str(i), questionDate=assigned)
        now = timezone.now()
        early, late = ts(now - timedelta(hours=5)), ts(now - timedelta(hours=1))
        Leetcode.objects.create(username='late', total_solved_dict={'1': late})
        Leetcode.objects.create(username='early', total_solved_dict={'1': early})
        Leetcode.objects.create(username='both', total_solved_dict={'1': late, '2': late})
        Leetcode.objects.create(username='none', total_solved_dict={})

    def test_ranking_and_tie_break(self):
        tasks.calculate_leaderboards()
        daily = Leaderboard.objects.get(leaderboard_type='daily').leaderboard_data
        self.assertEqual([daily[str(r)]['username'] for r in range(1, 5)], ['both', 'early', 'late', 'none'])
        self.assertEqual(Leetcode.objects.get(username='early').daily_rank, 2)

    def test_no_solves_has_no_last_solved_time(self):
        tasks.calculate_leaderboards()
        daily = Leaderboard.objects.get(leaderboard_type='daily').leaderboard_data
        self.assertIsNone(daily['4']['last_solv'])
        self.assertIsNotNone(daily['1']['last_solv'])


class TodayQuestionsTests(TestCase):
    def test_today_is_ist_day(self):
        user = User.objects.create_user('a@thapar.edu')
        Leetcode.objects.create(username='alice', user=user)
        # 00:30 IST is still "yesterday" in UTC
        Question.objects.create(leetcode_id=1, title='Early', titleSlug='early', questionDate=datetime(2026, 3, 10, 0, 30, tzinfo=IST))
        Question.objects.create(leetcode_id=2, title='Yesterday', titleSlug='yday', questionDate=datetime(2026, 3, 9, 23, 30, tzinfo=IST))
        client = APIClient()
        client.force_authenticate(user)
        with mock.patch('django.utils.timezone.now', return_value=datetime(2026, 3, 10, 12, 0, tzinfo=IST).astimezone(dt_timezone.utc)):
            res = client.get('/api/leaderboard/questions/today/')
        self.assertEqual([q['title'] for q in res.data], ['Early'])


class RefreshCommandTests(TestCase):
    def test_refreshes_every_user_then_rebuilds_leaderboards(self):
        Leetcode.objects.create(username='alice')
        Leetcode.objects.create(username='bob')
        with mock.patch.object(tasks, 'get_user_data') as get_user_data:
            call_command('refresh_leaderboard')
        self.assertEqual(sorted(c.args[0] for c in get_user_data.call_args_list), ['alice', 'bob'])
        self.assertEqual(Leaderboard.objects.count(), 3)
