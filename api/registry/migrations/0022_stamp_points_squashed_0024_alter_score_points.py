# Generated by Django 4.2.4 on 2023-09-22 21:31

from django.db import migrations, models


class Migration(migrations.Migration):

    replaces = [
        ("registry", "0022_stamp_points"),
        ("registry", "0023_remove_stamp_points_score_points"),
        ("registry", "0024_alter_score_points"),
    ]

    dependencies = [
        ("registry", "0021_alter_event_community"),
    ]

    operations = [
        migrations.AddField(
            model_name="score",
            name="points",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
