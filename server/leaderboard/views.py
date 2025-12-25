from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from .models import Leetcode, Question, Leaderboard
from .tasks import get_user_data
from .serializers import LeetCodeSerializer, QuestionSerializer

def get_today_questions(username):
    # "Today" in TIME_ZONE (IST), not UTC
    start_of_today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    questions = Question.objects.filter(questionDate__gte=start_of_today, questionDate__lt=start_of_today + timedelta(days=1))
    context = {'username': username}
    serializer = QuestionSerializer(questions, many=True, context=context)
    return serializer.data


class Register(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request,*args, **kwargs):
        user = request.user
        username = (request.data.get('username') or '').strip()
        if not username:
            return Response({"error": "Username is required"}, status=status.HTTP_400_BAD_REQUEST)
        if hasattr(user, 'leetcode'):
            return Response({"error": "A LeetCode account is already linked"}, status=status.HTTP_400_BAD_REQUEST)

        acc = Leetcode.objects.filter(username__iexact=username).first()
        if acc and acc.user_id is not None:
            return Response({"error": "This LeetCode account is already linked to another user"}, status=status.HTTP_400_BAD_REQUEST)
        if acc:
            # Claim an account left unlinked by the old auth system
            acc.user = user
            acc.save()
        else:
            acc = Leetcode.objects.create(username=username, user=user)
        print(f"User {user} registered with Leetcode username {username}")
        # Fetch their LeetCode profile now so the profile page isn't empty until the next refresh
        get_user_data(acc.username, acc.pk)
        return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)

class Profile(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, *args, **kwargs):
        account = getattr(request.user, 'leetcode', None)
        if account is None:
            return Response({"error": "No LeetCode account linked", "leetcode": False}, status=status.HTTP_404_NOT_FOUND)

        serializer = LeetCodeSerializer(account)
        return Response(serializer.data, status=status.HTTP_200_OK)

class GetQuestionsForTheDay(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, *args, **kwargs):
        try:
            account = getattr(request.user, 'leetcode', None)
            if account is None:
                return Response({"error": "No LeetCode account linked", "leetcode": False}, status=status.HTTP_404_NOT_FOUND)
            username = account.username
            questions_data = get_today_questions(username)
            return Response(questions_data, status=status.HTTP_200_OK)
        except Question.DoesNotExist:
            return Response({"error": "Questions not found"}, status=status.HTTP_404_NOT_FOUND)
        

class GetAllQuestions(APIView):
    def get(self, request, *args, **kwargs):
        try:
            questions = Question.objects.all()
            serializer = QuestionSerializer(questions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Question.DoesNotExist:
            return Response({"error": "Questions not found"}, status=status.HTTP_404_NOT_FOUND)

class DailyLeaderboard(APIView):
    def get(self, request, *args, **kwargs):
        try:
            one_day = Leaderboard.objects.get(leaderboard_type='daily').leaderboard_data
        except Leaderboard.DoesNotExist:
            return Response({"error": "Daily leaderboard not found"}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(one_day, status=status.HTTP_200_OK)

class WeeklyLeaderboard(APIView):
    def get(self, request, *args, **kwargs):
        try:
            one_week = Leaderboard.objects.get(leaderboard_type='weekly').leaderboard_data
        except Leaderboard.DoesNotExist:
            return Response({"error": "Weekly leaderboard not found"}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(one_week, status=status.HTTP_200_OK)

class MonthlyLeaderboard(APIView):
    def get(self, request, *args, **kwargs):
        try:
            one_month = Leaderboard.objects.get(leaderboard_type='monthly').leaderboard_data
        except Leaderboard.DoesNotExist:
            return Response({"error": "Monthly leaderboard not found"}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(one_month, status=status.HTTP_200_OK)
