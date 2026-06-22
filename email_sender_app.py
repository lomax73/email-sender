import streamlit as st
import pandas as pd
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import json
import re
from email_validator import validate_email, EmailNotValidError
import dns.resolver

CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

def is_valid_email(email, sender_email="test@example.com"):
    try:
        # 1. Validazione sintassi e dominio
        valid = validate_email(str(email), check_deliverability=True)
        domain = valid.domain
        
        # 2. Ottenere il record MX
        records = dns.resolver.resolve(domain, 'MX')
        mx_record = str(records[0].exchange)
        
        # 3. Connessione SMTP per verificare l'esistenza della mailbox
        server = smtplib.SMTP(timeout=5)
        server.set_debuglevel(0)
        
        server.connect(mx_record, 25)
        server.helo(server.local_hostname)
        server.mail(sender_email if sender_email else "test@example.com")
        code, message = server.rcpt(str(email))
        server.quit()
        
        # Il codice 250 o 251 indica che l'utente esiste (o il server accetta tutto)
        # Il codice 550 indica che l'utente NON esiste
        if code in (250, 251):
            return True
        else:
            return False
            
    except Exception:
        # Se c'è un errore (dominio inesistente, timeout, server irraggiungibile), consideriamo non valida
        return False

# Configurazione della pagina
st.set_page_config(page_title="Email Bulk Sender", layout="wide")

# Carica configurazione
config = load_config()

# Navigazione
st.sidebar.title("Menu")
page = st.sidebar.radio("Vai a", ["Invio Email", "Verifica Email"])

# --- SIDEBAR: Configurazione SMTP ---
st.sidebar.header("⚙️ Configurazione SMTP")
smtp_server = st.sidebar.text_input("Server SMTP", value=config.get("smtp_server", "smtp.gmail.com"))
smtp_port = st.sidebar.number_input("Porta SMTP", value=config.get("smtp_port", 587))
sender_email = st.sidebar.text_input("Email Mittente", value=config.get("sender_email", ""))
sender_password = st.sidebar.text_input("Password", type="password", value=config.get("sender_password", ""), help="Se usi Gmail, usa una 'Password per le app'")
email_subject = st.sidebar.text_input("Oggetto Email", value=config.get("email_subject", "Comunicazione Importante"))
delay_seconds = st.sidebar.slider("Intervallo tra invii (secondi)", 0, 60, config.get("delay_seconds", 2))

if st.sidebar.button("💾 Salva Impostazioni"):
    config["smtp_server"] = smtp_server
    config["smtp_port"] = smtp_port
    config["sender_email"] = sender_email
    config["sender_password"] = sender_password
    config["email_subject"] = email_subject
    config["delay_seconds"] = delay_seconds
    save_config(config)
    st.sidebar.success("Impostazioni salvate!")

if page == "Invio Email":
    st.image("Risorsa 1-100.jpg", width=200)
    st.title("📧 Invio Comunicazioni Massive")
    st.markdown("""
    Questa applicazione permette di inviare email personalizzate a una lista di contatti.
    Puoi caricare un file **CSV** o **Excel**, configurare i parametri SMTP e monitorare l'invio.
    """)

    st.sidebar.markdown("---")
    st.sidebar.subheader("🧪 Test Connessione")
    test_recipient = st.sidebar.text_input("Email di test (opzionale)", help="Inserisci un indirizzo email a cui inviare un messaggio di prova per verificare il corretto invio")

    if st.sidebar.button("🔌 Test Configurazione SMTP"):
        if not sender_email or not sender_password:
            st.sidebar.error("Inserisci email e password del mittente.")
        else:
            try:
                with st.sidebar.status("Verifica connessione in corso...", expanded=True) as status:
                    st.write("Connessione al server SMTP...")
                    server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
                    st.write("Avvio crittografia TLS...")
                    server.starttls()
                    st.write("Autenticazione in corso...")
                    server.login(sender_email, sender_password)
                    
                    if test_recipient:
                        st.write(f"Invio email di test a {test_recipient}...")
                        msg = MIMEMultipart()
                        msg['From'] = sender_email
                        msg['To'] = test_recipient
                        msg['Subject'] = "Test Email Massiva - Configurazione Corretta"
                        body = "Se ricevi questo messaggio, la configurazione SMTP del tuo inviatore di email massive è corretta e funzionante!"
                        msg.attach(MIMEText(body, 'plain'))
                        server.send_message(msg)
                        status.update(label="✅ Connessione riuscita ed email inviata!", state="complete", expanded=False)
                        st.sidebar.success("✅ Connessione riuscita ed email di prova inviata con successo!")
                    else:
                        status.update(label="✅ Connessione riuscita!", state="complete", expanded=False)
                        st.sidebar.success("✅ Connessione SMTP riuscita e credenziali corrette!")
                    
                    server.quit()
            except Exception as e:
                st.sidebar.error(f"❌ Errore durante il test: {e}")

    # --- MAIN: Caricamento File ---
    st.subheader("1. Carica la lista contatti")
    uploaded_file = st.file_uploader("Scegli un file CSV o Excel", type=["csv", "xlsx"])

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success(f"File caricato con successo! {len(df)} contatti trovati.")
            st.dataframe(df.head(), use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                email_col = st.selectbox("Seleziona la colonna delle Email", options=df.columns)
            with col2:
                name_col = st.selectbox("Seleziona la colonna del Nome (opzionale)", options=["Nessuno"] + list(df.columns))

            st.subheader("2. Componi il messaggio")
            st.info("Puoi usare `{Nome}` nel testo per personalizzare il messaggio con il valore della colonna selezionata.")
            email_body = st.text_area("Corpo dell'email", height=200, value="Gentile {Nome},\n\nquesta è una comunicazione automatica.")

            if st.checkbox("Mostra anteprima prima email"):
                sample_name = df.iloc[0][name_col] if name_col != "Nessuno" else "Cliente"
                preview_text = email_body.replace("{Nome}", str(sample_name))
                st.markdown("---")
                st.write(f"**A:** {df.iloc[0][email_col]}")
                st.write(f"**Oggetto:** {email_subject}")
                st.write("**Corpo:**")
                st.text(preview_text)
                st.markdown("---")

            st.subheader("3. Avvia Spedizione")
            if st.button("🚀 Inizia Invio Email"):
                if not sender_email or not sender_password:
                    st.error("Per favore, inserisci email e password del mittente nella barra laterale.")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results = []

                    try:
                        server = smtplib.SMTP(smtp_server, smtp_port)
                        server.starttls()
                        server.login(sender_email, sender_password)

                        for index, row in df.iterrows():
                            recipient_email = row[email_col]
                            recipient_name = row[name_col] if name_col != "Nessuno" else "Cliente"
                            
                            personalized_body = email_body.replace("{Nome}", str(recipient_name))
                            
                            msg = MIMEMultipart()
                            msg['From'] = sender_email
                            msg['To'] = recipient_email
                            msg['Subject'] = email_subject
                            msg.attach(MIMEText(personalized_body, 'plain'))

                            try:
                                server.send_message(msg)
                                results.append({"Email": recipient_email, "Stato": "Inviata", "Errore": ""})
                            except Exception as e:
                                results.append({"Email": recipient_email, "Stato": "Errore", "Errore": str(e)})

                            progress = (index + 1) / len(df)
                            progress_bar.progress(progress)
                            status_text.text(f"Invio a {recipient_email} ({index + 1}/{len(df)})")
                            
                            if index < len(df) - 1:
                                time.sleep(delay_seconds)

                        server.quit()
                        st.success("Operazione completata!")

                    except Exception as e:
                        st.error(f"Errore di connessione SMTP: {e}")

                    if results:
                        report_df = pd.DataFrame(results)
                        st.subheader("📊 Report Spedizione")
                        st.dataframe(report_df, use_container_width=True)
                        
                        csv_report = report_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Scarica Report CSV",
                            data=csv_report,
                            file_name="report_spedizione_email.csv",
                            mime="text/csv"
                        )

        except Exception as e:
            st.error(f"Errore nella lettura del file: {e}")
    else:
        st.info("In attesa del caricamento di un file...")

elif page == "Verifica Email":
    st.image("Risorsa 1-100.jpg", width=200)
    st.title("✅ Verifica Validità Email")
    st.markdown("Carica un file per verificare se gli indirizzi email contenuti sono validi nel formato.")

    uploaded_file = st.file_uploader("Scegli un file CSV o Excel per la verifica", type=["csv", "xlsx"])

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success(f"File caricato con successo! {len(df)} righe trovate.")
            st.dataframe(df.head(), use_container_width=True)
            
            email_col = st.selectbox("Seleziona la colonna delle Email da verificare", options=df.columns)
            
            if st.button("🔍 Avvia Verifica"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                results = []

                for index, row in df.iterrows():
                    email = row[email_col]
                    is_valid = is_valid_email(email, sender_email=sender_email)
                    results.append({"Email": email, "Valida": "Sì" if is_valid else "No"})
                    
                    progress = (index + 1) / len(df)
                    progress_bar.progress(progress)
                    status_text.text(f"Verifica: {email} ({index + 1}/{len(df)})")

                st.success("Verifica completata!")
                
                report_df = pd.DataFrame(results)
                
                valid_count = len(report_df[report_df['Valida'] == 'Sì'])
                invalid_count = len(report_df[report_df['Valida'] == 'No'])
                st.write(f"**Email Valide:** {valid_count} | **Email Non Valide:** {invalid_count}")

                st.dataframe(report_df, use_container_width=True)
                
                csv_report = report_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Scarica Report Verifica CSV",
                    data=csv_report,
                    file_name="report_verifica_email.csv",
                    mime="text/csv"
                )

        except Exception as e:
            st.error(f"Errore nella lettura del file: {e}")
