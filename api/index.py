import os
import sys
from django.core.wsgi import get_wsgi_application

# Add the project root directory to the Python path
path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if path not in sys.path:
    sys.path.append(path)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Vercel looks for a variable named "app"
app = get_wsgi_application()