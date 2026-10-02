PYTEST = .venv/bin/pytest
TEST_ENV = DB_HOST=localhost DB_PORT=5433

.PHONY: setup test test-income test-balance test-one

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r ../valueinvesting/requirements.txt -r requirements.txt

test:
	$(TEST_ENV) $(PYTEST) -s -v

test-income:
	$(TEST_ENV) $(PYTEST) -s -v fundamentals_consistency/test_income_statement.py

test-balance:
	$(TEST_ENV) $(PYTEST) -s -v fundamentals_consistency/test_balance_sheet.py

test-cf:
	$(TEST_ENV) $(PYTEST) -s -v fundamentals_consistency/test_cash_flow.py


test-one:
	$(TEST_ENV) $(PYTEST) -s -v $(T)
