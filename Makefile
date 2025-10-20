.PHONY: init ingest serve clean
init:
	@test -d .venv || python3 -m venv .venv
	@. .venv/bin/activate && python -m pip install --upgrade pip && pip install -r requirements.txt
	@echo "Activate: source .venv/bin/activate"
ingest:
	@. .venv/bin/activate && python -m scripts.ingest
serve:
	@. .venv/bin/activate && uvicorn app.api.main:app --reload --port $${APP_PORT:-8000}
clean:
	rm -rf data/cache/* data/tmp/* data/scratch/*
