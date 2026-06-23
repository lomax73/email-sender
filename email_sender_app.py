import streamlit as st
import pandas as pd
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import os
import json
import re
from email_validator import validate_email, EmailNotValidError
import dns.resolver
from datetime import datetime
from fpdf import FPDF
import shutil

CONFIG_FILE = "config.json"
HISTORY_FILE = "history.json"
REPORTS_DIR = "reports"

if not os.path.exists(REPORTS_DIR):
    os.makedirs(REPORTS_DIR)

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

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)

def generate_pdf_report(activity_type, results_df, start_time, end_time, subject="", body="", parameters=None):
    if parameters is None:
        parameters = {}
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    pdf.cell(200, 10, txt=f"Report: {activity_type}", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Inizio: {start_time}", ln=True, align='L')
    pdf.cell(200, 10, txt=f"Fine: {end_time}", ln=True, align='L')
    
    if parameters:
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(200, 10, txt="Parametri Utilizzati:", ln=True, align='L')
        pdf.set_font("Arial", '', 10)
        for k, v in parameters.items():
            pdf.cell(200, 8, txt=f"- {k}: {v}", ln=True, align='L')
            
    if subject:
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(200, 10, txt=f"Oggetto: {subject.encode('latin-1', 'replace').decode('latin-1')}", ln=True, align='L')
    if body:
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(200, 10, txt="Testo Email:", ln=True, align='L')
        pdf.set_font("Arial", '', 10)
        pdf.multi_cell(0, 5, txt=body.encode('latin-1', 'replace').decode('latin-1'))
        pdf.ln()
    
    pdf.set_font("Arial", size=12)
    total = len(results_df)
    if activity_type == "Invio Email":
        success = len(results_df[results_df["Stato"] == "Inviata"])
        errors = total - success
    else:
        success = len(results_df[results_df["Valida"] == "Sì"])
        errors = total - success

    pdf.cell(200, 10, txt=f"Totale: {total} | Successi: {success} | Errori: {errors}", ln=True, align='L')
    pdf.cell(200, 10, txt="", ln=True)
    
    pdf.set_font("Arial", 'B', 9)
    col_width = 190 / len(results_df.columns)
    for col in results_df.columns:
        pdf.cell(col_width, 10, str(col), border=1)
    pdf.ln()
    
    pdf.set_font("Arial", '', 8)
    for index, row in results_df.iterrows():
        for item in row:
            text = str(item)[:40].encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(col_width, 10, text, border=1)
        pdf.ln()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{activity_type.replace(' ', '_')}_{timestamp}.pdf"
    filepath = os.path.join(REPORTS_DIR, filename)
    pdf.output(filepath)
    return filepath

def send_report_email(filepath, sender_email, sender_password, smtp_server, smtp_port, activity_type):
    if not sender_email or not sender_password:
        return
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = sender_email
        msg['Subject'] = f"Report Automatico: {activity_type}"
        
        body_text = f"In allegato il report relativo all'operazione: {activity_type}"
        msg.attach(MIMEText(body_text, 'plain'))
        
        with open(filepath, "rb") as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(filepath))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(filepath)}"'
            msg.attach(part)
            
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        st.error(f"Errore nell'invio del report via email: {e}")

def is_valid_email(email, sender_email="test@example.com"):
    try:
        valid = validate_email(str(email), check_deliverability=True)
        domain = valid.domain
        
        records = dns.resolver.resolve(domain, 'MX')
        mx_record = str(records[0].exchange)
        
        server = smtplib.SMTP(timeout=5)
        server.set_debuglevel(0)
        
        server.connect(mx_record, 25)
        server.helo(server.local_hostname)
        server.mail(sender_email if sender_email else "test@example.com")
        code, message = server.rcpt(str(email))
        server.quit()
        
        if code in (250, 251):
            return True
        else:
            return False
            
    except Exception:
        return False

# Configurazione della pagina
st.set_page_config(page_title="Email Bulk Sender Pro", layout="wide")

# Carica configurazione
config = load_config()

# --- LOGIN SYSTEM ---
if not st.session_state.get('authenticated', False):
    col_img1, col_img2, col_img3 = st.columns([5,2,5])
    with col_img2:
        if os.path.exists("Risorsa 1-100.jpg"):
            st.image("Risorsa 1-100.jpg", use_container_width=True)
        
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("Accesso Riservato")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Accedi")
            
            if submit:
                app_user = config.get("app_username", "admin")
                app_pass = config.get("app_password", "admin")
                if username == app_user and password == app_pass:
                    st.session_state['authenticated'] = True
                    st.rerun()
                else:
                    st.error("Credenziali non valide")
    st.stop()

def logout():
    st.session_state['authenticated'] = False

# Navigazione
st.sidebar.title("Menu")
page = st.sidebar.radio("Vai a", ["Invio Email", "Verifica Email", "Storico Attività", "Impostazioni App"])
st.sidebar.button("🚪 Esci", on_click=logout)

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
    if os.path.exists("Risorsa 1-100.jpg"):
        st.image("Risorsa 1-100.jpg", width=200)
    st.title("📧 Invio Comunicazioni Massive")

    st.sidebar.markdown("---")
    st.sidebar.subheader("🧪 Test Connessione")
    test_recipient = st.sidebar.text_input("Email di test (opzionale)")

    if st.sidebar.button("🔌 Test Configurazione SMTP"):
        if not sender_email or not sender_password:
            st.sidebar.error("Inserisci email e password del mittente.")
        else:
            try:
                with st.sidebar.status("Verifica connessione in corso...", expanded=True) as status:
                    server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
                    server.starttls()
                    server.login(sender_email, sender_password)
                    
                    if test_recipient:
                        msg = MIMEMultipart()
                        msg['From'] = sender_email
                        msg['To'] = test_recipient
                        msg['Subject'] = "Test Email Massiva - Configurazione Corretta"
                        msg.attach(MIMEText("Test di funzionamento.", 'plain'))
                        server.send_message(msg)
                        status.update(label="✅ Connessione riuscita ed email inviata!", state="complete", expanded=False)
                        st.sidebar.success("✅ Connessione riuscita ed email di prova inviata con successo!")
                    else:
                        status.update(label="✅ Connessione riuscita!", state="complete", expanded=False)
                        st.sidebar.success("✅ Connessione SMTP riuscita e credenziali corrette!")
                    
                    server.quit()
            except Exception as e:
                st.sidebar.error(f"❌ Errore durante il test: {e}")

    st.subheader("1. Carica la lista contatti")
    uploaded_file = st.file_uploader("Scegli un file CSV o Excel", type=["csv", "xlsx"])

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success(f"File caricato con successo! {len(df)} contatti trovati.")
            
            col1, col2 = st.columns(2)
            with col1:
                email_col = st.selectbox("Seleziona la colonna delle Email", options=df.columns)
            with col2:
                name_col = st.selectbox("Seleziona la colonna del Nome (opzionale)", options=["Nessuno"] + list(df.columns))

            st.subheader("2. Componi il messaggio")
            st.info("Puoi usare `{Nome}` nel testo per personalizzare il messaggio con il valore della colonna selezionata.")
            
            is_html = st.checkbox("Usa formato HTML", value=False)
            email_body = st.text_area("Corpo dell'email", height=200, value="Gentile {Nome},\n\nquesta è una comunicazione automatica.")
            
            st.subheader("3. Allegati (Opzionale)")
            uploaded_attachments = st.file_uploader("Carica uno o più allegati", accept_multiple_files=True)

            if st.checkbox("Mostra anteprima prima email"):
                sample_name = df.iloc[0][name_col] if name_col != "Nessuno" else "Cliente"
                preview_text = email_body.replace("{Nome}", str(sample_name))
                st.markdown("---")
                st.write(f"**A:** {df.iloc[0][email_col]}")
                st.write(f"**Oggetto:** {email_subject}")
                st.write("**Corpo:**")
                if is_html:
                    st.markdown(preview_text, unsafe_allow_html=True)
                else:
                    st.text(preview_text)
                st.markdown("---")

            st.subheader("4. Avvia Spedizione")
            if st.button("🚀 Inizia Invio Email"):
                if not sender_email or not sender_password:
                    st.error("Per favore, inserisci email e password del mittente nella barra laterale.")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results = []
                    start_time = datetime.now()

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
                            
                            if is_html:
                                msg.attach(MIMEText(personalized_body, 'html'))
                            else:
                                msg.attach(MIMEText(personalized_body, 'plain'))
                            
                            if uploaded_attachments:
                                for file in uploaded_attachments:
                                    file.seek(0)
                                    part = MIMEApplication(file.read(), Name=file.name)
                                    part['Content-Disposition'] = f'attachment; filename="{file.name}"'
                                    msg.attach(part)

                            try:
                                server.send_message(msg)
                                results.append({"Email": recipient_email, "Stato": "Inviata", "Errore": ""})
                            except Exception as e:
                                results.append({"Email": recipient_email, "Stato": "Errore", "Errore": str(e)})

                            progress = (index + 1) / len(df)
                            progress_bar.progress(progress)
                            status_text.text(f"Invio a {recipient_email} ({index + 1}/{len(df)})")
                            
                            if index < len(df) - 1 and delay_seconds > 0:
                                countdown_text = st.empty()
                                countdown_bar = st.progress(0)
                                for t in range(delay_seconds, 0, -1):
                                    countdown_text.text(f"Attesa di {t} secondi prima della prossima email...")
                                    countdown_bar.progress(t / delay_seconds)
                                    time.sleep(1)
                                countdown_text.empty()
                                countdown_bar.empty()

                        server.quit()
                        st.success("Operazione completata!")

                    except Exception as e:
                        st.error(f"Errore di connessione SMTP: {e}")

                    if results:
                        end_time = datetime.now()
                        report_df = pd.DataFrame(results)
                        st.subheader("📊 Report Spedizione")
                        st.dataframe(report_df, use_container_width=True)
                        
                        parameters = {
                            "Server SMTP": smtp_server,
                            "Porta SMTP": smtp_port,
                            "Email Mittente": sender_email,
                            "Intervallo (sec)": delay_seconds,
                            "Formato HTML": "Sì" if is_html else "No"
                        }
                        pdf_path = generate_pdf_report("Invio Email", report_df, start_time.strftime("%Y-%m-%d %H:%M:%S"), end_time.strftime("%Y-%m-%d %H:%M:%S"), subject=email_subject, body=email_body, parameters=parameters)
                        send_report_email(pdf_path, sender_email, sender_password, smtp_server, smtp_port, "Invio Email")
                        
                        history = load_history()
                        history.append({
                            "data": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "tipo": "Invio Email",
                            "totale": len(report_df),
                            "successi": len(report_df[report_df["Stato"] == "Inviata"]),
                            "errori": len(report_df[report_df["Stato"] == "Errore"]),
                            "pdf_path": pdf_path
                        })
                        save_history(history)
                        
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                label="📥 Scarica Report PDF",
                                data=f,
                                file_name=os.path.basename(pdf_path),
                                mime="application/pdf"
                            )

        except Exception as e:
            st.error(f"Errore nella lettura del file: {e}")
    else:
        st.info("In attesa del caricamento di un file...")

elif page == "Verifica Email":
    if os.path.exists("Risorsa 1-100.jpg"):
        st.image("Risorsa 1-100.jpg", width=200)
    st.title("✅ Verifica Validità Email")

    uploaded_file = st.file_uploader("Scegli un file CSV o Excel per la verifica", type=["csv", "xlsx"])

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success(f"File caricato con successo! {len(df)} righe trovate.")
            email_col = st.selectbox("Seleziona la colonna delle Email da verificare", options=df.columns)
            
            if st.button("🔍 Avvia Verifica"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                results = []
                start_time = datetime.now()

                for index, row in df.iterrows():
                    email = row[email_col]
                    is_valid = is_valid_email(email, sender_email=sender_email)
                    results.append({"Email": email, "Valida": "Sì" if is_valid else "No"})
                    
                    progress = (index + 1) / len(df)
                    progress_bar.progress(progress)
                    status_text.text(f"Verifica: {email} ({index + 1}/{len(df)})")

                st.success("Verifica completata!")
                end_time = datetime.now()
                
                report_df = pd.DataFrame(results)
                
                valid_count = len(report_df[report_df['Valida'] == 'Sì'])
                invalid_count = len(report_df[report_df['Valida'] == 'No'])
                st.write(f"**Email Valide:** {valid_count} | **Email Non Valide:** {invalid_count}")

                st.dataframe(report_df, use_container_width=True)
                
                parameters = {"Email Mittente": sender_email}
                pdf_path = generate_pdf_report("Verifica Email", report_df, start_time.strftime("%Y-%m-%d %H:%M:%S"), end_time.strftime("%Y-%m-%d %H:%M:%S"), parameters=parameters)
                send_report_email(pdf_path, sender_email, sender_password, smtp_server, smtp_port, "Verifica Email")
                
                history = load_history()
                history.append({
                    "data": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "tipo": "Verifica Email",
                    "totale": len(report_df),
                    "successi": valid_count,
                    "errori": invalid_count,
                    "pdf_path": pdf_path
                })
                save_history(history)
                
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="📥 Scarica Report Verifica PDF",
                        data=f,
                        file_name=os.path.basename(pdf_path),
                        mime="application/pdf"
                    )

        except Exception as e:
            st.error(f"Errore nella lettura del file: {e}")

elif page == "Storico Attività":
    if os.path.exists("Risorsa 1-100.jpg"):
        st.image("Risorsa 1-100.jpg", width=200)
    st.title("📜 Storico Attività")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("Consulta le attività passate e scarica i relativi report.")
    with col2:
        if st.button("🗑️ Cancella tutto lo storico"):
            save_history([])
            if os.path.exists(REPORTS_DIR):
                shutil.rmtree(REPORTS_DIR)
            os.makedirs(REPORTS_DIR)
            st.success("Storico e report cancellati.")
            st.rerun()
            
    history = load_history()
    if not history:
        st.info("Nessuna attività registrata finora.")
    else:
        hist_df = pd.DataFrame(history)
        st.dataframe(hist_df, use_container_width=True)
        
        st.subheader("Scarica Report")
        for entry in reversed(history):
            if os.path.exists(entry['pdf_path']):
                with open(entry['pdf_path'], "rb") as f:
                    st.download_button(
                        label=f"📥 Scarica {entry['tipo']} del {entry['data']} (PDF)",
                        data=f,
                        file_name=os.path.basename(entry['pdf_path']),
                        mime="application/pdf",
                        key=entry['pdf_path']
                    )

elif page == "Impostazioni App":
    if os.path.exists("Risorsa 1-100.jpg"):
        st.image("Risorsa 1-100.jpg", width=200)
    st.title("🔐 Impostazioni App")
    
    with st.form("change_credentials_form"):
        new_username = st.text_input("Nuovo Username", value=config.get("app_username", "admin"))
        new_password = st.text_input("Nuova Password", type="password")
        confirm_password = st.text_input("Conferma Nuova Password", type="password")
        
        if st.form_submit_button("Aggiorna Credenziali"):
            if new_password != confirm_password:
                st.error("Le password non coincidono!")
            elif len(new_password) < 4:
                st.error("La password deve essere di almeno 4 caratteri.")
            else:
                config["app_username"] = new_username
                config["app_password"] = new_password
                save_config(config)
                st.success("Credenziali aggiornate con successo!")

