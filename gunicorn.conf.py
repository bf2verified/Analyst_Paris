"""Config gunicorn — lit PORT depuis l'environnement, pas du shell."""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
workers = 1
threads = 2
timeout = 120
preload_app = True
accesslog = "-"
errorlog = "-"
loglevel = "info"
# Utile pour voir les erreurs d'import tôt
capture_output = True
