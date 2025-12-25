python manage.py collectstatic --noinput
# Refresh LeetCode data and leaderboards in the background, every 2 minutes
python manage.py refresh_leaderboard --every 120 &
python manage.py runserver 0.0.0.0:8000
