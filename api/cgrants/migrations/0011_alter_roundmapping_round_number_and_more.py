# Generated by Django 4.2.6 on 2024-03-12 07:24

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cgrants", "0010_alter_roundmapping_round_number"),
    ]

    operations = [
        migrations.AlterField(
            model_name="roundmapping",
            name="round_number",
            field=models.CharField(
                default="",
                help_text="GG Round number associated with round address",
                max_length=100,
            ),
        ),
        migrations.AlterField(
            model_name="squelchedaccounts",
            name="round_number",
            field=models.CharField(
                default="",
                help_text="GG Round number associated with round address",
                max_length=100,
            ),
        ),
    ]
