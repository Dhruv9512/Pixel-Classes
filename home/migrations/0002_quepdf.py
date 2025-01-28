# Generated by Django 5.1.4 on 2025-01-28 15:25

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuePdf',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('pdf', models.CharField(max_length=255)),
                ('sem', models.IntegerField()),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='home.courselist')),
            ],
        ),
    ]
