# Generated by Django 4.2.4 on 2023-09-18 11:26

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0016_accountapikey_create_scorers_and_more"),
        ("registry", "0019_rename_event_index_score_history_index"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="community",
            field=models.ForeignKey(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="event",
                to="account.community",
            ),
        ),
    ]
