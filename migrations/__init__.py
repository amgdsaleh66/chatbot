# مجلد Migrations
# في MVP نستخدم SQLAlchemy create_all مباشرةً عند بدء التطبيق.
# لإضافة Alembic في المرحلة الثانية:
#   pip install alembic
#   alembic init migrations
#   alembic revision --autogenerate -m "initial"
#   alembic upgrade head