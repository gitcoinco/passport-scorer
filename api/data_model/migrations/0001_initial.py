# Generated by Django 4.2.6 on 2024-04-11 15:36

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Cache",
            fields=[
                (
                    "key",
                    models.CharField(max_length=128, primary_key=True, serialize=False),
                ),
                ("value", models.JSONField()),
                ("updated_at", models.DateTimeField()),
            ],
            options={
                "db_table": "cache",
                "managed": False,
            },
        ),
    ]
