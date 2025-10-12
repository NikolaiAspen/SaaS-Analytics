"""
Email service for sending notifications
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        from_email: str,
        from_name: str = "SaaS Analytics"
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.from_name = from_name

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ) -> bool:
        """Send an email"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg['Date'] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

            # Add text part (fallback)
            if text_body:
                part1 = MIMEText(text_body, 'plain', 'utf-8')
                msg.attach(part1)

            # Add HTML part
            part2 = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(part2)

            # Connect to SMTP server and send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    def send_version_release_notification(
        self,
        to_email: str,
        version: str,
        release_notes: str,
        dashboard_url: str = "https://accounting.fangstr.com"
    ) -> bool:
        """Send version release notification email"""
        subject = f"🚀 Ny versjon {version} av SaaS Analytics"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .header .version {{
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 8px 16px;
            border-radius: 20px;
            margin-top: 10px;
            font-size: 14px;
            font-weight: 600;
        }}
        .content {{
            padding: 30px;
            color: #333;
            line-height: 1.6;
        }}
        .content h2 {{
            color: #667eea;
            font-size: 18px;
            margin-top: 0;
        }}
        .release-notes {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            white-space: pre-wrap;
        }}
        .cta {{
            text-align: center;
            padding: 20px 30px;
        }}
        .cta a {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            padding: 14px 32px;
            border-radius: 8px;
            font-weight: 600;
            transition: transform 0.2s;
        }}
        .cta a:hover {{
            transform: translateY(-2px);
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #999;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Ny Versjon Lansert!</h1>
            <div class="version">Versjon {version}</div>
        </div>
        <div class="content">
            <h2>Hva er nytt?</h2>
            <div class="release-notes">{release_notes}</div>
        </div>
        <div class="cta">
            <a href="{dashboard_url}">Åpne Dashboard</a>
        </div>
        <div class="footer">
            SaaS Analytics - MRR/Churn analyse med Niko insights<br>
            <a href="{dashboard_url}" style="color: #667eea; text-decoration: none;">accounting.fangstr.com</a>
        </div>
    </div>
</body>
</html>
"""

        text_body = f"""
Ny versjon {version} av SaaS Analytics!

Hva er nytt:
{release_notes}

Åpne dashboard: {dashboard_url}

---
SaaS Analytics - MRR/Churn analyse med Niko insights
"""

        return self.send_email(to_email, subject, html_body, text_body)

    def send_welcome_email(
        self,
        to_email: str,
        password: str,
        dashboard_url: str = "https://accounting.fangstr.com"
    ) -> bool:
        """Send welcome email with login credentials"""
        subject = "Velkommen til SaaS Analytics 👋"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #3ddc97 0%, #20a774 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .content {{
            padding: 30px;
            color: #333;
            line-height: 1.6;
        }}
        .credentials {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #3ddc97;
            margin: 20px 0;
        }}
        .credentials strong {{
            color: #20a774;
        }}
        .cta {{
            text-align: center;
            padding: 20px 30px;
        }}
        .cta a {{
            display: inline-block;
            background: linear-gradient(135deg, #3ddc97 0%, #20a774 100%);
            color: white;
            text-decoration: none;
            padding: 14px 32px;
            border-radius: 8px;
            font-weight: 600;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #999;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>👋 Velkommen til SaaS Analytics!</h1>
        </div>
        <div class="content">
            <p>Din konto har blitt opprettet og du har nå tilgang til SaaS Analytics dashboard.</p>

            <div class="credentials">
                <p><strong>E-post:</strong> {to_email}</p>
                <p><strong>Passord:</strong> {password}</p>
            </div>

            <p><strong>Viktig:</strong> Vennligst endre passordet ditt første gang du logger inn.</p>

            <h3>Hva kan du gjøre med SaaS Analytics?</h3>
            <ul>
                <li>📊 Se MRR/ARR trender i sanntid</li>
                <li>📈 Følg churn og kundevekst</li>
                <li>🔮 Få AI-drevne innsikter fra Niko</li>
                <li>💰 Analyser faktura og abonnementsdata</li>
            </ul>
        </div>
        <div class="cta">
            <a href="{dashboard_url}">Logg inn nå</a>
        </div>
        <div class="footer">
            SaaS Analytics - MRR/Churn analyse med Niko insights
        </div>
    </div>
</body>
</html>
"""

        text_body = f"""
Velkommen til SaaS Analytics!

Din konto har blitt opprettet:

E-post: {to_email}
Passord: {password}

Viktig: Vennligst endre passordet ditt første gang du logger inn.

Logg inn her: {dashboard_url}

---
SaaS Analytics - MRR/Churn analyse med Niko insights
"""

        return self.send_email(to_email, subject, html_body, text_body)
