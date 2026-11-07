from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('cleaning', '0016_schedulerequest')]

    operations = [
        migrations.AddField(
            model_name='schedulerequest',
            name='task_id',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
