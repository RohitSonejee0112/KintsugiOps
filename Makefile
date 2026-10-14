.PHONY: help install test run dashboard seed clean

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies in virtual environment"
	@echo "  make test       - Run full pytest test suite"
	@echo "  make run        - Run FastAPI mock ITSM server"
	@echo "  make dashboard  - Launch Streamlit interactive dashboard"
	@echo "  make seed       - Generate and seed 500 synthetic tickets"
	@echo "  make clean      - Clean cache and temporary files"

install:
	python -m pip install -e ".[dev]"

test:
	pytest tests/ -v

run:
	uvicorn src.mock_itsm.main:app --reload --port 8000

dashboard:
	streamlit run src/dashboard/app.py

seed:
	python -c "from src.simulation.generator import seed_synthetic_tickets; seed_synthetic_tickets(500); print('Seeded 500 tickets.')"

clean:
	rm -rf .pytest_cache htmlcov .coverage dist build *.egg-info
