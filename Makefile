api-test:
	cd apps/api && uv run pytest

web-test:
	cd apps/web && pnpm test

email-test:
	cd apps/email-worker && pnpm test

test: api-test web-test email-test
