from django.utils import timezone
from datetime import datetime, timedelta, timezone as dt_timezone
from .models import Leetcode, LeaderboardEntry, Question, Leaderboard
from .query_manager import *
import logging
import time

logger = logging.getLogger(__name__)

# LeetCode's full problem list rarely changes, so each worker process caches it
# instead of downloading ~3,500 questions for every user on every refresh.
ALL_QUESTIONS_TTL = 60 * 60
_all_questions_cache = {'fetched_at': 0.0, 'questions': []}

# JSONField round-trips dict keys as strings, so question ids are always stored as str.

def get_latest_submissions(submissions):
    latest_submissions = {}
    for submission in submissions:
        question_id = str(submission[0])
        timestamp = int(submission[2])
        if question_id not in latest_submissions or timestamp > latest_submissions[question_id]:
            latest_submissions[question_id] = timestamp
    return latest_submissions

def get_assigned_questions():
    return [
        [question.leetcode_id, question.titleSlug, question.questionDate.timestamp()]
        for question in Question.objects.all()
    ] # [leetcode_id, titleSlug, timestamp]

def match_questions_to_solved(questions, solved_submissions: dict):
    matched_ques: dict = {}
    for question in questions:
        question_id = str(question[0])
        question_timestamp = question[2]
        solved_timestamp = solved_submissions.get(question_id)
        if solved_timestamp is not None and solved_timestamp > question_timestamp:
            matched_ques[question_id] = solved_timestamp
    return matched_ques

def cal_solved_intervals(questions, solved_dict: dict):
    current_time = timezone.now()
    one_day_interval = (current_time - timedelta(days=1)).timestamp()
    one_week_interval = (current_time - timedelta(weeks=1)).timestamp()
    one_month_interval = (current_time - timedelta(days=30)).timestamp()  # Approximation for a month

    solved_within_one_day = {}
    solved_within_one_week = {}
    solved_within_one_month = {}

    for question in questions:
        question_id = str(question[0])
        question_timestamp = question[2]
        ques_solved_timestamp = solved_dict.get(question_id)
        if ques_solved_timestamp is None:
            continue
        if ques_solved_timestamp < question_timestamp:
            continue  # Skip if question was solved before it was assigned

        if ques_solved_timestamp >= one_day_interval:
            solved_within_one_day[question_id] = ques_solved_timestamp
        if ques_solved_timestamp >= one_week_interval:
            solved_within_one_week[question_id] = ques_solved_timestamp
        if ques_solved_timestamp >= one_month_interval:
            solved_within_one_month[question_id] = ques_solved_timestamp

    return solved_within_one_day, solved_within_one_week, solved_within_one_month

def fetch_user_profile(username):
    try:
        response = send_query(MATCHED_USER_QUERY, {"username": username})
        if response:
            return response['data']['matchedUser']['profile']
    except Exception:
        logger.exception("Error fetching user profile for %s", username)
    return None

def fetch_submitted_questions(username, limit=500):
    try:
        return send_query(QUESTIONS_SUBMITTED_QUERY, {"username": username, "limit": limit})['data']['recentAcSubmissionList']
    except Exception:
        logger.exception("Error fetching submitted questions for %s", username)
    return []

def fetch_language_problem_count(username):
    try:
        return send_query(LANGUAGE_PROBLEM_COUNT_QUERY, {"username": username})['data']['matchedUser']['languageProblemCount']
    except Exception:
        logger.exception("Error fetching language problem count for %s", username)
    return []

def fetch_all_questions():
    if _all_questions_cache['questions'] and time.monotonic() - _all_questions_cache['fetched_at'] < ALL_QUESTIONS_TTL:
        return _all_questions_cache['questions']
    try:
        query_vars = {"categorySlug": "all-code-essentials", "skip": 0, "limit": 5000, "filters": {}}
        questions = send_query(ALL_QUESTION_LIST_QUERY, query_vars)['data']['problemsetQuestionList']['questions']
    except Exception:
        logger.exception("Error fetching all questions")
        return _all_questions_cache['questions']  # stale list beats no list
    _all_questions_cache.update(fetched_at=time.monotonic(), questions=questions)
    return questions

def get_user_instance(id):
    try:
        return Leetcode.objects.get(pk=id)
    except Leetcode.DoesNotExist:
        logger.warning("Leetcode account with id %s does not exist", id)
    return None

def update_user_instance(instance: Leetcode, user_data, matched_questions, latest_solved, total_solved, language_problem_count):
    instance.name = user_data.get('realName', '')
    instance.leetcode_rank = user_data.get('ranking', '')
    instance.photo_url = user_data.get('userAvatar', '')
    instance.total_solved = sum(question['problemsSolved'] for question in language_problem_count)
    instance.matched_ques = len(matched_questions)
    instance.submission_dict = latest_solved
    instance.matched_ques_dict = matched_questions
    instance.total_solved_dict = total_solved
    instance.save()

def process_submissions(submitted_questions, all_question_list):
    titleSlug_to_id = {question['titleSlug']: question['frontendQuestionId'] for question in all_question_list}
    return [
        [titleSlug_to_id[question['titleSlug']], question['titleSlug'], question['timestamp']]
        for question in submitted_questions if question['titleSlug'] in titleSlug_to_id
    ] # [leetcode_id, titleSlug, timestamp]

def generate_leaderboards_entries():
    ques_given = get_assigned_questions()
    for user_instance in Leetcode.objects.all():
        solved_dict = user_instance.total_solved_dict or {}
        intervals = dict(zip(('day', 'week', 'month'), cal_solved_intervals(ques_given, solved_dict)))
        for interval, solved in intervals.items():
            entry, _ = LeaderboardEntry.objects.get_or_create(user=user_instance, interval=interval)
            entry.questions_solved = len(solved)
            entry.last_solved_timestamp = max(solved.values(), default=0)
            entry.save()
    logger.info("Leaderboard entries generated successfully")

def format_timestamp(timestamp):
    if not timestamp:
        return None
    return timezone.localtime(datetime.fromtimestamp(timestamp, tz=dt_timezone.utc)).strftime('%Y-%m-%d %H:%M:%S')

def update_rank(user_list, rank_dict, rank_type):
    for idx, (user_obj, ques_solv, last_solv) in enumerate(user_list):
        rank_dict[idx+1] = {
            "username": user_obj.username,
            "photo_url": user_obj.photo_url,
            "ques_solv": ques_solv,
            "last_solv": format_timestamp(last_solv),
        }
        setattr(user_obj, rank_type, idx+1)
        user_obj.save(update_fields=[rank_type])

def calculate_leaderboards():
    generate_leaderboards_entries()
    boards = {'day': [], 'week': [], 'month': []}

    for entry in LeaderboardEntry.objects.select_related('user'):
        if entry.interval in boards:
            boards[entry.interval].append([entry.user, entry.questions_solved, entry.last_solved_timestamp])

    # Most solved first; ties go to whoever finished their last question earlier
    results = {}
    for interval, leaderboard_type, rank_type in (
        ('day', 'daily', 'daily_rank'),
        ('week', 'weekly', 'weekly_rank'),
        ('month', 'monthly', 'monthly_rank'),
    ):
        board = boards[interval]
        board.sort(key=lambda x: (-x[1], x[2]))
        rank_dict = {}
        update_rank(board, rank_dict, rank_type)
        Leaderboard.objects.update_or_create(
            leaderboard_type=leaderboard_type, defaults={'leaderboard_data': rank_dict}
        )
        results[leaderboard_type] = rank_dict

    logger.info("Leaderboards calculated successfully")
    return results

def get_user_data(username, id):
    try:
        user_profile = fetch_user_profile(username)
        if not user_profile:
            logger.warning("No profile data found for user %s", username)
            return

        submitted_questions = fetch_submitted_questions(username)
        language_problem_count = fetch_language_problem_count(username)
        all_question_list = fetch_all_questions()

        submissions = process_submissions(submitted_questions, all_question_list)
        latest_solved = get_latest_submissions(submissions)

        user_instance = get_user_instance(id)
        if not user_instance:
            return

        # LeetCode only exposes recent submissions, so keep every solve we've ever seen
        total_solved = {str(k): v for k, v in (user_instance.total_solved_dict or {}).items()}
        for ques, solved_at in latest_solved.items():
            total_solved.setdefault(ques, solved_at)

        matched_ques = match_questions_to_solved(get_assigned_questions(), total_solved)
        update_user_instance(user_instance, user_profile, matched_ques, latest_solved, total_solved, language_problem_count)

        logger.info("Data for %s saved successfully", username)
    except Exception:
        logger.exception("Error fetching or updating data for user %s", username)

def refresh_user_data():
    """Fetch every user's latest LeetCode data, then rebuild the leaderboards."""
    for user in Leetcode.objects.all():
        get_user_data(user.username, user.id)
    calculate_leaderboards()
