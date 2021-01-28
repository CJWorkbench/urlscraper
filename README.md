# urlscraper

Download a list of URLs into a table.

# Development

First, set up your enviroment. It's just Docker.

Run `docker build .` to test that everything works.

Then do the Development Dance:

1. Write a failing test to `tests/`
2. Run `docker build .` to test it fails
3. Fix the code so all tests pass
4. Submit a pull request

# Deployment

1. Edit the version in `pyproject.toml`
2. Write an entry to `CHANGELOG.md`
3. Run `docker build .` one last time
4. `git push`
