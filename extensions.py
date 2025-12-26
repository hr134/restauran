from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_migrate import Migrate
from flask_caching import Cache
from flask_compress import Compress

db = SQLAlchemy()
mail = Mail()
migrate = Migrate()
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})
compress = Compress()
