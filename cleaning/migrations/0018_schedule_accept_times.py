from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('cleaning', '0017_schedulerequest_task_id')]

    operations = [
        migrations.AddField(
            model_name='cleaningschedule',
            name='accepted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='cleaningschedule',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
