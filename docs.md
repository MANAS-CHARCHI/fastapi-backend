alembic init alembic

docker-compose run backend alembic  revision --autogenerate -m "New Migration"

docker-compose run backend alembic upgrade head