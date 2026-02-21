.PHONY: build run stop logs clean restart

build:
	docker-compose build

run:
	docker-compose up -d

stop:
	docker-compose down

logs:
	docker-compose logs -f

restart:
	docker-compose restart

clean:
	docker-compose down --rmi all --volumes

status:
	docker-compose ps

shell:
	docker-compose exec regime-engine /bin/bash
