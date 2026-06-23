#!/bin/bash
cd "$(dirname "$0")"
echo "Sto caricando le ultime modifiche su GitHub..."
git add .
git commit -m "Aggiornamento automatico app"
git push origin main
echo "==========================================="
echo "✅ Aggiornamento caricato con successo!"
echo "Ora Streamlit Cloud aggiornerà l'app in pochi secondi."
echo "==========================================="
sleep 4
