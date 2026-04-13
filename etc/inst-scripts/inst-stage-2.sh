
(
echo "Performing 2nd stage installation for Litestar-Pulse"

# run this under the base directory of the installation
cd ${VVG_BASEDIR}
micromamba install -y uv

# create minimal pyproject.toml
# project version should be current date

VERSION=$(date +%y%m%d)
cat > pyproject.toml <<EOL
[project]
name = "${uMAMBA_ENVNAME}-venv"
version = "${VERSION}"
requires-python = ">=3.12"
dependencies = []
EOL

# add internal dependencies
uv add --editable envs/tagato
uv add --editable envs/litestar-pulse
uv sync

# create instances directory
mkdir -p instances

)

# EOF
