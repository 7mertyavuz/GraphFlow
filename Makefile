.PHONY: help setup demo download build-matrix dev-api dev-ui test audit benchmark openapi

PYTHON ?= .venv/bin/python
PYTEST ?= .venv/bin/pytest
UVICORN ?= .venv/bin/uvicorn

help:
	@echo "GraphFlow — Makefile Hedefleri / Targets:"
	@echo "  make setup        Python sanal ortamı ve frontend paketlerini kur / Install venv & npm deps"
	@echo "  make demo         ~5 saniyede sentetik demo korpusu üret (data/demo) / Generate demo corpus"
	@echo "  make download     Binance arşiv verisini indir / Download real Binance klines"
	@echo "  make build-matrix Arama matrislerini inşa et / Build memory-mapped search matrices"
	@echo "  make dev-api      FastAPI sunucusunu başlat (port 8000) / Run API server"
	@echo "  make dev-ui       Next.js arayüzünü başlat (port 3000) / Run UI dev server"
	@echo "  make test         Tüm birim ve değişmezlik testlerini koş / Run pytest & tsc"
	@echo "  make audit        14x14 çapraz formasyon denetimini koş / Run formation cross-audit"
	@echo "  make benchmark    Ground-truth kesinlik/duyarlılık ölçümünü koş / Run GT benchmark"
	@echo "  make openapi      OpenAPI şemasından TypeScript tiplerini üret / Regenerate frontend types"

setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements.txt
	cd frontend && npm install

demo:
	$(PYTHON) -m tools.generate_demo_corpus --out data/demo

download:
	$(PYTHON) -m engine.ingest.download --timeframes 1d 4h
	$(PYTHON) -m tools.backfill --timeframe 4h

build-matrix:
	$(PYTHON) -m engine.matrix.build

dev-api:
	$(UVICORN) engine.api.main:app --reload --port 8000

dev-ui:
	cd frontend && npm run dev

test:
	$(PYTEST) -q -k "not test_real_store_is_fresh"
	cd frontend && npx tsc --noEmit

audit:
	$(PYTHON) -m tools.formation_audit --cross

benchmark:
	$(PYTHON) -m tools.gt_benchmark --family all

openapi:
	$(PYTHON) -c "import json, engine.api.main; open('frontend/openapi.json','w',encoding='utf-8').write(json.dumps(engine.api.main.app.openapi(), indent=2, ensure_ascii=False))"
	cd frontend && npx openapi-typescript openapi.json -o src/types/api.ts
