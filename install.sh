#!/usr/bin/bash

# installation script for litestar-pulse [https://github.com/trmznt/litestar-pulse]

# optional variable:
# - VVG_BASEDIR
# - VVG_EXCLUDE
# - LITESTAR_PULSE_REPOURL

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
if [ -t 0 ] && [ -z "${VVG_BASEDIR:-}" ]; then
  printf "Base installation directory? [./litestar-pulse] "
  read VVG_BASEDIR
fi

# default value
VVG_BASEDIR="${VVG_BASEDIR:-./litestar-pulse}"

PIXI_ENVNAME="${PIXI_ENVNAME:-litestar-pulse}"

# for dev: source <(curl -L https://raw.githubusercontent.com/vivaxgen/vvg-box/refs/heads/dev/install.sh)

# create an EXCLUDE variable and add snakemake if the EXCLUDE variable is already exists
PYVER=3.14
VVG_EXCLUDE="${VVG_EXCLUDE:-}:snakemake"
source <(curl -L https://raw.githubusercontent.com/vivaxgen/vvg-box/main/install.sh)


echo "Cloning litestar-pulse"
# add --branch dev for dev
git clone --depth 1 ${LITESTAR_PULSE_REPOURL:-https://github.com/trmznt/litestar-pulse.git} ${ENVS_DIR}/litestar-pulse

# perform 2nd stage installation for litestar-pulse
source ${ENVS_DIR}/litestar-pulse/etc/inst-scripts/inst-stage-2.sh

# generate directory for instances
mkdir -p ${VVG_BASEDIR}/instances

# add to installed-repo.txt
echo "litestar-pulse" >> ${ETC_DIR}/installed-repo.txt

echo
echo "litestar-pulse has been successfully installed. "
echo "Please read the docs for further setup."
echo "The base installation directory (VVG_BASEDIR) is:"
echo
echo "$(realpath "${VVG_BASEDIR}")"
echo
echo "To activate the basic litestar-pulse environment (eg. for installing"
echo "or setting up base enviroment directory), execute the command:"
echo
echo "    $(realpath "${BINDIR}/activate")"
echo

# EOF