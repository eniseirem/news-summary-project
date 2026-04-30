#!/usr/bin/env bash
# Generate README.pdf from README.md (run from n8n directory).
# Requires: pandoc (recommended) or Node.js for npx md-to-pdf.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
README_MD="${SCRIPT_DIR}/README.md"
README_PDF="${SCRIPT_DIR}/README.pdf"

if [ ! -f "$README_MD" ]; then
  echo "Error: README.md not found at $README_MD"
  exit 1
fi

if command -v pandoc >/dev/null 2>&1; then
  echo "Using pandoc to generate PDF..."
  if pandoc "$README_MD" -o "$README_PDF" \
    --pdf-engine=pdflatex \
    -V geometry:margin=1in \
    -V colorlinks=true \
    -V linkcolor=blue \
    -V urlcolor=blue \
    --toc \
    --toc-depth=2 2>/dev/null; then
    echo "Created: $README_PDF"
    exit 0
  fi
  echo "pandoc failed (e.g. missing pdflatex). Trying npx md-to-pdf..."
fi

if command -v npx >/dev/null 2>&1; then
  echo "Using npx md-to-pdf to generate PDF..."
  npx --yes md-to-pdf "$README_MD"
  echo "Created: $README_PDF"
  exit 0
fi

echo "No PDF converter found. Install one of:"
echo "  • pandoc (recommended): https://pandoc.org/installing.html"
echo "    - macOS: brew install pandoc basictex"
echo "    - Ubuntu: sudo apt-get install pandoc texlive-xetex"
echo "  • Node.js, then run: npx md-to-pdf README.md  (creates README.pdf in same dir)"
exit 1
