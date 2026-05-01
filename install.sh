#!/usr/bin/bash

# installation script for litestar-pulse [https://github.com/trmznt/litestar-pulse]

# optional variable:
# - BASEDIR
# - OMIT

set -eu

# run the base.sh
# Detect the shell from which the script was called
parent=$(ps -o comm $PPID |tail -1)
parent=${parent#-}  # remove the leading dash that login shells have
case "$parent" in
  # shells supported by `micromamba shell init`
  bash|fish|xonsh|zsh)
    shell=$parent
    ;;
  *)
    # use the login shell (basename of $SHELL) as a fallback
    shell=${SHELL##*/}
    ;;
esac

# Parsing arguments
if [ -t 0 ] && [ -z "${BASEDIR:-}" ]; then
  printf "Base installation directory? [./litestar-pulse] "
  read BASEDIR
fi

# default value
BASEDIR="${BASEDIR:-./litestar-pulse}"

uMAMBA_ENVNAME="${uMAMBA_ENVNAME:-litestar-pulse}"

mkdir -p ${BASEDIR}/instances/

# for dev: source <(curl -L https://raw.githubusercontent.com/vivaxgen/vvg-box/refs/heads/dev/install.sh)

# create an EXCLUDE variable and add snakemake if the EXCLUDE variable is already exists
EXCLUDE="${EXCLUDE:-}:snakemake"
source <(curl -L https://raw.githubusercontent.com/vivaxgen/vvg-box/main/install.sh)

echo "Cloning tagato"
git clone --depth 1 https://github.com/trmznt/tagato.git ${ENVS_DIR}/tagato

echo "Cloning litestar-pulse"
# add --branch dev for dev
git clone --depth 1 https://github.com/trmznt/litestar-pulse.git ${ENVS_DIR}/litestar-pulse

# perform 2nd stage installation for litestar-pulse
source ${ENVS_DIR}/litestar-pulse/etc/inst-scripts/inst-stage-2.sh

# add to installed-repo.txt
echo "tagato" >> ${ETC_DIR}/installed-repo.txt
echo "litestar-pulse" >> ${ETC_DIR}/installed-repo.txt

echo
echo "litestar-pulse has been successfully installed. "
echo "Please read the docs for further setup."
echo "The base installation directory (VVG_BASEDIR) is:"
echo
echo `realpath ${BASEDIR}`
echo
echo "To activate the basic litestar-pulse environment (eg. for installing"
echo "or setting up base enviroment directory), execute the command:"
echo
echo `realpath ${BASEDIR}`/bin/activate
echo

# EOF