import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from skills.base import BaseSkill


class EmailSender(BaseSkill):
    """
    Skill untuk mengirim email melalui server SMTP.
    Mendukung pengiriman email dengan body HTML/plain text dan lampiran file.
    """
    
    name = "email_sender"
    description = "Kirim email melalui SMTP dengan dukungan lampiran"
    
    def get_parameters(self):
        return {
            "smtp_server": {
                "type": "string",
                "description": "Alamat server SMTP (contoh: smtp.gmail.com)",
                "required": True
            },
            "smtp_port": {
                "type": "integer",
                "description": "Port SMTP (default: 587 untuk TLS)",
                "required": False,
                "default": 587
            },
            "username": {
                "type": "string",
                "description": "Username/email pengirim",
                "required": True
            },
            "password": {
                "type": "string",
                "description": "Password atau App Password",
                "required": True
            },
            "to_email": {
                "type": "string",
                "description": "Alamat email penerima (pisahkan dengan koma untuk multiple)",
                "required": True
            },
            "subject": {
                "type": "string",
                "description": "Subjek email",
                "required": True
            },
            "body": {
                "type": "string",
                "description": "Isi email (teks atau HTML)",
                "required": True
            },
            "is_html": {
                "type": "boolean",
                "description": "Apakah body berformat HTML? (default: False)",
                "required": False,
                "default": False
            },
            "attachments": {
                "type": "string",
                "description": "Path file lampiran, pisahkan dengan koma jika lebih dari satu",
                "required": False,
                "default": ""
            },
            "use_tls": {
                "type": "boolean",
                "description": "Gunakan TLS? (default: True)",
                "required": False,
                "default": True
            }
        }
    
    def execute(self, params):
        smtp_server = params["smtp_server"]
        smtp_port = params.get("smtp_port", 587)
        username = params["username"]
        password = params["password"]
        to_email = params["to_email"]
        subject = params["subject"]
        body = params["body"]
        is_html = params.get("is_html", False)
        attachments = params.get("attachments", "")
        use_tls = params.get("use_tls", True)
        
        try:
            # Buat pesan email
            msg = MIMEMultipart()
            msg["From"] = username
            msg["To"] = to_email
            msg["Subject"] = subject
            
            # Tambahkan body email
            if is_html:
                msg.attach(MIMEText(body, "html", "utf-8"))
            else:
                msg.attach(MIMEText(body, "plain", "utf-8"))
            
            # Tambahkan lampiran jika ada
            attachment_list = [a.strip() for a in attachments.split(",") if a.strip()]
            
            for file_path in attachment_list:
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    
                    encoders.encode_base64(part)
                    filename = os.path.basename(file_path)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename= {filename}"
                    )
                    msg.attach(part)
                else:
                    return {
                        "success": False,
                        "error": f"File lampiran tidak ditemukan: {file_path}"
                    }
            
            # Kirim email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if use_tls:
                    server.starttls()
                server.login(username, password)
                server.send_message(msg)
            
            return {
                "success": True,
                "message": f"Email berhasil dikirim ke {to_email}",
                "subject": subject,
                "attachments_count": len(attachment_list)
            }
            
        except smtplib.SMTPAuthenticationError:
            return {
                "success": False,
                "error": "Autentikasi gagal. Periksa username dan password Anda."
            }
        except smtplib.SMTPException as e:
            return {
                "success": False,
                "error": f"Error SMTP: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error: {str(e)}"
            }
