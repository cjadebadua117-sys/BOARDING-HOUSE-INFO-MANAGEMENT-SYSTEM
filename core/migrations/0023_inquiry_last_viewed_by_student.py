from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_alter_boardinghouse_description_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='inquiry',
            name='last_viewed_by_student',
            field=models.DateTimeField(
                blank=True,
                help_text='When the student last opened this inquiry thread.',
                null=True,
            ),
        ),
    ]
