"""Run a disposable Django database for browser tests; never touches Back-End/db.sqlite3."""
import os
import sys
from pathlib import Path

frontend = Path(__file__).resolve().parent.parent
backend = frontend.parent / 'Back-End'
state = frontend / '.test-state'
state.mkdir(exist_ok=True)
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['WELLIFY_SQLITE_PATH'] = str(state / 'browser.sqlite3')
os.environ['WELLIFY_DEBUG'] = 'True'
os.environ['FRONTEND_ORIGINS'] = 'http://127.0.0.1:5174'
sys.path.insert(0, str(backend))
import django
django.setup()
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.db import connection

if connection.settings_dict['ENGINE'] != 'django.db.backends.sqlite3' or Path(connection.settings_dict['NAME']).resolve() != (state / 'browser.sqlite3').resolve():
    raise RuntimeError('Browser tests must use the isolated SQLite database.')
call_command('migrate', interactive=False, verbosity=0)
call_command('flush', interactive=False, verbosity=0)
call_command('seed_demo', verbosity=0)
User = get_user_model()
staff, _ = User.objects.get_or_create(username='browser_test_staff', defaults={'email': 'staff@wellify.example'})
staff.is_staff = True
staff.is_active = True
staff.set_password('Browser-Tests-Only-28!')
staff.save()
call_command('runserver', '127.0.0.1:8011', use_reloader=False)
