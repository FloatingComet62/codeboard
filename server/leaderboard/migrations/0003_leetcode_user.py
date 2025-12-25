# Leetcode.user used to point at ccs_auth.CUser (varchar email PK). It now points at
# accounts.User. 0002 was edited to no longer create the field so that it doesn't
# depend on AUTH_USER_MODEL; this migration drops any old column and re-adds it.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def drop_old_user_column(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        columns = [c.name for c in connection.introspection.get_table_description(cursor, 'leaderboard_leetcode')]
    if 'user_id' in columns:
        schema_editor.execute('ALTER TABLE leaderboard_leetcode DROP COLUMN user_id')


class Migration(migrations.Migration):

    dependencies = [
        ('leaderboard', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(drop_old_user_column, migrations.RunPython.noop),
        migrations.AddField(
            model_name='leetcode',
            name='user',
            field=models.OneToOneField(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]
