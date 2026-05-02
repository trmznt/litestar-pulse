
echo "Performing 2nd stage installation for Litestar-Pulse"

source ${ENVS_DIR}/vvg-box/etc/functions

# if envs/tagato directory does not exists, clone the tagato repository
if [ ! -d ${ENVS_DIR}/tagato" ]; then
    echo "Cloning tagato"
    git clone --depth 1 https://github.com/trmznt/tagato.git ${ENVS_DIR}/tagato
    echo "tagato" >> ${ETC_DIR}/installed-repo.txt
fi

(
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

# source vvg-box/etc/functions

# add internal dependencies
uv add --editable envs/tagato
uv add --editable envs/litestar-pulse
uv sync

# create instances directory
mkdir -p instances

)

# EOF
