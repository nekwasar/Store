.PHONY: build up down logs shell backup setup-token dev prod

build:
	docker compose -f docker-compose.prod.yml build

up:
	docker compose -f docker-compose.prod.yml up -d

down:
	docker compose -f docker-compose.prod.yml down

logs:
	docker compose -f docker-compose.prod.yml logs -f --tail=100

shell:
	docker compose -f docker-compose.prod.yml exec fastapi sh

backup:
	docker compose -f docker-compose.prod.yml exec mongo sh -c 'mongodump --archive=/data/db/backup.archive --authenticationDatabase admin -u $$MONGO_INITDB_ROOT_USERNAME -p $$MONGO_INITDB_ROOT_PASSWORD' && \
	docker compose -f docker-compose.prod.yml cp mongo:/data/db/backup.archive ./backups/backup-$$(date +%Y%m%d-%H%M).archive

setup-token:
	docker compose -f docker-compose.prod.yml exec fastapi python scripts/create-setup-token --base-url ${BASE_URL:-http://localhost:8989}

dev:
	docker compose -f docker-compose.dev.yml up -d --build

dev-down:
	docker compose -f docker-compose.dev.yml down

restart:
	docker compose -f docker-compose.prod.yml restart

ps:
	docker compose -f docker-compose.prod.yml ps
