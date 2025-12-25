import time
import traceback

from django.core.management.base import BaseCommand

from leaderboard.tasks import refresh_user_data


class Command(BaseCommand):
    help = "Fetch every user's LeetCode data and rebuild the leaderboards."

    def add_arguments(self, parser):
        parser.add_argument('--every', type=int, metavar='SECONDS',
                            help='Keep running, refreshing every SECONDS instead of once')

    def handle(self, *args, every=None, **options):
        if not every:
            refresh_user_data()
            return

        while True:
            try:
                refresh_user_data()
            except Exception:
                # Keep looping; the next run may succeed (e.g. if LeetCode was down)
                self.stderr.write(traceback.format_exc())
            time.sleep(every)
