# Procfile for Render deployment
# This tells Render how to run your application

# Use gunicorn for production (more stable than Flask dev server)
web: gunicorn --worker-class eventlet -w 1 app:app --bind 0.0.0.0:$PORT --timeout 120
