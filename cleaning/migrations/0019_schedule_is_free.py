from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('cleaning', '0018_schedule_accept_times')]

    operations = [
        migrations.AddField(
            model_name='cleaningschedule',
            name='is_free',
            field=models.BooleanField(default=False),
        ),
    ]
