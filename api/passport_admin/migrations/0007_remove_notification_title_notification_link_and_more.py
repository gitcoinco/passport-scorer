# Generated by Django 4.2.6 on 2024-06-20 15:03

import account.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("passport_admin", "0006_notificationstatus_delete_dismissednotification"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="notification",
            name="title",
        ),
        migrations.AddField(
            model_name="notification",
            name="link",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="notification",
            name="link_text",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="notification",
            name="eth_address",
            field=account.models.EthAddressField(max_length=42, null=True),
        ),
        migrations.AlterField(
            model_name="notification",
            name="type",
            field=models.CharField(
                choices=[
                    ("custom", "Custom"),
                    ("stamp_expiry", "Stamp Expiry"),
                    ("on_chain_expiry", "OnChain Expiry"),
                    ("deduplication", "Deduplication"),
                ],
                db_index=True,
                default="custom",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="notificationstatus",
            name="eth_address",
            field=account.models.EthAddressField(max_length=42),
        ),
    ]
