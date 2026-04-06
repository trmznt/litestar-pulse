

micromamba install -y uv

# create minimal pyproject.toml
# project version should be current date + XX (2 digit)
cat >> pyproject.toml <<EOL
[project]
name = "messy2-server"
version = "1"
requires-python = ">=3.11"
dependencies = []
EOL

# add internal dependencies
uv add envs/tagato
uv add envs/litestar-pulse

# create instance directory
