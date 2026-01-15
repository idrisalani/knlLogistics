release: python manage.py migrate && python manage.py collectstatic --noinput
web: gunicorn knlLogistics.wsgi:application --bind 0.0.0.0:$PORT