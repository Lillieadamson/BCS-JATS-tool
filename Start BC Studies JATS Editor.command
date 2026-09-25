#!/bin/bash
# Double-click this file to start the BC Studies JATS editor.
#
# It creates a local Python environment the first time it runs (and again if
# a Python upgrade breaks it), installs the dependencies, starts the web app,
# and opens it in your browser. Closing the Terminal window stops the app.

cd "$(dirname "$0")" || exit 1

python3 -c 'import sys; sys.exit(sys.version_info < (3,10))' || {
  echo "This tool needs Python 3.10 or newer. Install it from python.org, then double-click again."; read -r; exit 1; }

# a venv broken by a Python upgrade gets rebuilt
if [ -d venv ] && ! venv/bin/python -c '' 2>/dev/null; then rm -rf venv; fi
if [ ! -d venv ]; then
  echo "Setting up for the first time. This takes a minute..."
  python3 -m venv venv || { echo "Could not create the Python environment."; read -r; exit 1; }
fi

# shellcheck disable=SC1091
source venv/bin/activate

# install only on first run or when requirements.txt changes, so the tool
# still starts offline
if [ ! -f venv/.installed ] || [ requirements.txt -nt venv/.installed ]; then
  python -m pip install --quiet -r requirements.txt || {
    echo "Could not install dependencies. Are you online?"; read -r; exit 1; }
  touch venv/.installed
fi

echo ""
echo "BC Studies JATS editor is starting at http://localhost:5002"
echo "Leave this window open while you work. Close it to stop."
echo ""
( sleep 2 && open http://localhost:5002 ) &
python app.py
