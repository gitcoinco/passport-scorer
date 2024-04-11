# Generated by Django 4.2.6 on 2024-04-11 11:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stake", "0003_alter_stake_chain_alter_stakeevent_chain"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stake",
            name="current_amount",
            field=models.DecimalField(
                decimal_places=18,
                help_text="Summary stake amount (uint256)",
                max_digits=78,
            ),
        ),
    ]
