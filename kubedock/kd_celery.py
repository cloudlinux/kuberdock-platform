"""Creates an instance of celery application to use it in different modules.
"""

from .factory import make_celery

celery = make_celery()
