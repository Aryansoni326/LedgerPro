from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0004_alter_auditlog_action_alter_auditlog_resource_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='resource_type',
            field=models.CharField(
                choices=[
                    ('bill', 'Bill'),
                    ('import_export_record', 'Import-Export Record'),
                    ('eway_bill_record', 'E-Way Bill Record'),
                    ('document', 'Document'),
                    ('agent_approval', 'Agent Approval'),
                    ('transaction', 'Transaction'),
                    ('risk_signal', 'Risk Signal'),
                ],
                max_length=40,
            ),
        ),
    ]
