docker-compose build --no-cache

alembic init alembic

docker-compose run backend alembic revision --autogenerate -m "models"

docker-compose run backend alembic revision --autogenerate -m "tokenblacklist: create blacklist table-2"

docker-compose run backend alembic upgrade head