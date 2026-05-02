
echo "Performing 2nd stage installation for Litestar-Pulse"

source ${ENVS_DIR}/vvg-box/etc/functions

# if envs/tagato directory does not exists, clone the tagato repository
if [ ! -d "${ENVS_DIR}/tagato" ]; then
    echo "Cloning tagato"
    git clone --depth 1 https://github.com/trmznt/tagato.git ${ENVS_DIR}/tagato
    echo "tagato" >> ${ETC_DIR}/installed-repo.txt
fi

# run this under the base directory of the installation
micromamba install -y uv

# create minimal pyproject.toml
# project version should be current date

# if pyproject.toml already exists, skip this step
if [ -f "pyproject.toml" ]; then
    echo "pyproject.toml already exists, skipping creation"
else

VERSION=$(date +%y%m%d)
cat > ${VVG_BASEDIR}/pyproject.toml <<EOL
[project]
name = "${uMAMBA_ENVNAME}-venv"
version = "${VERSION}"
requires-python = "${PYVER}"
dependencies = []
EOL

fi

# source vvg-box/etc/functions

# add uv internal dependencies
(
    cd ${VVG_BASEDIR}
    uv add --editable envs/tagato
    uv add --editable envs/litestar-pulse
    uv sync
)



# EOF
