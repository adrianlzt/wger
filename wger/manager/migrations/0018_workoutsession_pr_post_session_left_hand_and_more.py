# Generated by Django 4.2.6 on 2024-01-16 07:16

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("manager", "0017_alter_workoutlog_exercise_base"),
    ]

    operations = [
        migrations.AddField(
            model_name="workoutsession",
            name="pr_post_session_left_hand",
            field=models.FloatField(
                blank=True,
                help_text="Personal record after the session (left hand, kg)",
                null=True,
                verbose_name="Post-session PR (left hand)",
            ),
        ),
        migrations.AddField(
            model_name="workoutsession",
            name="pr_post_session_right_hand",
            field=models.FloatField(
                blank=True,
                help_text="Personal record after the session (right hand, kg)",
                null=True,
                verbose_name="Post-session PR (right hand)",
            ),
        ),
        migrations.AddField(
            model_name="workoutsession",
            name="pr_pre_session_left_hand",
            field=models.FloatField(
                blank=True,
                help_text="Personal record before the session (left hand, kg)",
                null=True,
                verbose_name="Pre-session PR (left hand)",
            ),
        ),
        migrations.AddField(
            model_name="workoutsession",
            name="pr_pre_session_right_hand",
            field=models.FloatField(
                blank=True,
                help_text="Personal record before the session (right hand, kg)",
                null=True,
                verbose_name="Pre-session PR (right hand)",
            ),
        ),
    ]
