general_elections:
	uv run python election_stats.py

primary_elections:
	uv run python election_stats.py --stage Primaries --min-year=1996
