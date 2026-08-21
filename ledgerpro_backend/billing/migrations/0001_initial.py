# Generated manually for billing.Subscription + UsagePeriod

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import billing.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tier', models.CharField(
                    choices=[
                        ('free', 'Free'),
                        ('starter', 'Starter'),
                        ('growth', 'Growth'),
                        ('professional', 'Professional'),
                        ('enterprise', 'Enterprise'),
                    ],
                    db_index=True,
                    default='free',
                    max_length=32,
                )),
                ('status', models.CharField(
                    choices=[
                        ('trialing', 'Trialing'),
                        ('active', 'Active'),
                        ('past_due', 'Past Due'),
                        ('canceled', 'Canceled'),
                    ],
                    db_index=True,
                    default='active',
                    max_length=20,
                )),
                ('custom_config', models.JSONField(blank=True, default=dict)),
                ('trial_ends_at', models.DateTimeField(blank=True, null=True)),
                ('current_period_start', models.DateField(default=billing.models.current_period_start)),
                ('current_period_end', models.DateField(default=billing.models.current_period_end)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='subscription',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.CreateModel(
            name='UsagePeriod',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('period_start', models.DateField()),
                ('period_end', models.DateField()),
                ('documents_count', models.PositiveIntegerField(default=0)),
                ('ai_queries_count', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('subscription', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='usage_periods',
                    to='billing.subscription',
                )),
            ],
        ),
        migrations.AddIndex(
            model_name='subscription',
            index=models.Index(fields=['tier', 'status'], name='billing_sub_tier_6c1a0d_idx'),
        ),
        migrations.AddIndex(
            model_name='usageperiod',
            index=models.Index(fields=['subscription', 'period_start'], name='billing_usa_subscri_0f3c2a_idx'),
        ),
        migrations.AddConstraint(
            model_name='usageperiod',
            constraint=models.UniqueConstraint(
                fields=('subscription', 'period_start'),
                name='uq_usage_subscription_period',
            ),
        ),
    ]
