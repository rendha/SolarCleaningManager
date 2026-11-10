from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('cleaning', '0019_schedule_is_free')]

    operations = [
        migrations.AlterField(
            model_name='cleaningschedule',
            name='status',
            field=models.CharField(
                choices=[('Scheduled', 'Scheduled'), ('Completed', 'Completed'), ('Partially done', 'Partially done'),
                         ('Rescheduled', 'Rescheduled'), ('Cancelled', 'Cancelled')],
                default='Scheduled', max_length=20),
        ),
    ]
