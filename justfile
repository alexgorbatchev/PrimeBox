# PrimeBox task automation

default: test

# Run test suite
test:
    uv run python -m unittest discover -s tests -v

# Run test coverage check
coverage:
    uv run coverage run -m unittest discover -s tests
    uv run coverage report -m

# Run launcher setup (human mode)
run-launcher *args:
    uv run primebox-launcher {{args}}

# Run launcher setup (token-conservative agent mode)
run-launcher-ai *args:
    AGENT=1 uv run primebox-launcher {{args}}
