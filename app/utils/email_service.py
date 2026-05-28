import os
import resend

resend.api_key = os.getenv("RESEND_API_KEY")

FROM_EMAIL = "IIoT Security <onboarding@resend.dev>"


def send_verification_email(to_email: str, code: str, name: str):
    """إرسال كود تحقق عند التسجيل"""
    resend.Emails.send({
        "from":    FROM_EMAIL,
        "to":      [to_email],
        "subject": "Verify your email — IIoT Security Platform",
        "html":    f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #1a1a2e;">Welcome to IIoT Security Platform</h2>
            <p>Hello <strong>{name}</strong>,</p>
            <p>Please verify your email address using the code below:</p>
            <div style="background: #f4f4f4; padding: 20px; text-align: center; border-radius: 8px; margin: 20px 0;">
                <h1 style="color: #e63946; letter-spacing: 8px; font-size: 36px;">{code}</h1>
            </div>
            <p>This code expires in <strong>10 minutes</strong>.</p>
            <p>If you didn't create an account, please ignore this email.</p>
        </div>
        """
    })


def send_email_change_request(to_email: str, code: str, name: str):
    """إرسال كود تحقق للإيميل الجديد"""
    resend.Emails.send({
        "from":    FROM_EMAIL,
        "to":      [to_email],
        "subject": "Confirm your new email — IIoT Security Platform",
        "html":    f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #1a1a2e;">Email Change Request</h2>
            <p>Hello <strong>{name}</strong>,</p>
            <p>Use this code to confirm your new email address:</p>
            <div style="background: #f4f4f4; padding: 20px; text-align: center; border-radius: 8px; margin: 20px 0;">
                <h1 style="color: #e63946; letter-spacing: 8px; font-size: 36px;">{code}</h1>
            </div>
            <p>This code expires in <strong>10 minutes</strong>.</p>
        </div>
        """
    })


def send_notification_email(to_email: str, name: str, subject: str, message: str):
    """إرسال إشعار من Super Admin لشركة"""
    resend.Emails.send({
        "from":    FROM_EMAIL,
        "to":      [to_email],
        "subject": f"{subject} — IIoT Security Platform",
        "html":    f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #1a1a2e;">IIoT Security Platform</h2>
            <p>Hello <strong>{name}</strong>,</p>
            <div style="background: #f4f4f4; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p>{message}</p>
            </div>
            <p style="color: #666; font-size: 12px;">This is an automated message from IIoT Security Platform.</p>
        </div>
        """
    })


def send_email_change_notification(to_email: str, new_email: str, name: str, accept_token: str, reject_token: str, base_url: str):
    """إشعار للإيميل القديم مع خيار قبول أو رفض"""
    resend.Emails.send({
        "from":    FROM_EMAIL,
        "to":      [to_email],
        "subject": "Email change notification — IIoT Security Platform",
        "html":    f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #1a1a2e;">Email Change Notification</h2>
            <p>Hello <strong>{name}</strong>,</p>
            <p>A request was made to change your account email to: <strong>{new_email}</strong></p>
            <p>If this was you, click <strong>Accept</strong>. If not, click <strong>Reject</strong> immediately.</p>
            <div style="margin: 30px 0; text-align: center;">
                <a href="{base_url}/auth/email-change/accept?token={accept_token}"
                   style="background: #22c55e; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; margin-right: 10px;">
                   Accept
                </a>
                <a href="{base_url}/auth/email-change/reject?token={reject_token}"
                   style="background: #ef4444; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none;">
                   Reject
                </a>
            </div>
            <p style="color: #666; font-size: 12px;">This link expires in 24 hours.</p>
        </div>
        """
    })