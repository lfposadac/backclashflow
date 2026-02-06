from functools import wraps

import requests as http_client
from flask import Flask, jsonify, request
from flask_cors import CORS

from config import Config

app = Flask(__name__)
app.config.from_object(Config)

CORS(app, origins=Config.ALLOWED_ORIGINS)


# ---------------------------------------------------------------------------
# Autenticacion por API Key
# ---------------------------------------------------------------------------
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key != app.config["API_KEY"]:
            return jsonify({"error": "API key invalida o no proporcionada"}), 401
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Resend - Envio de correo
# ---------------------------------------------------------------------------
def send_email(to_email, subject, html_body):
    response = http_client.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {app.config['RESEND_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "from": app.config["MAIL_FROM"],
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        },
        timeout=30,
    )

    if response.status_code not in (200, 201):
        raise Exception(f"Resend error ({response.status_code}): {response.text}")

    return response.json()


# ---------------------------------------------------------------------------
# Formateo de datos
# ---------------------------------------------------------------------------
def format_currency(amount, currency="COP"):
    return f"${amount:,.0f} {currency}"


def format_date(date_str):
    if not date_str:
        return "N/A"
    try:
        from datetime import datetime
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y %H:%M")
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return date_str


# ---------------------------------------------------------------------------
# Template HTML del correo
# ---------------------------------------------------------------------------
def build_payment_email_html(data: dict) -> str:
    creator_name = data.get("creator_name", "Usuario")
    amount = data.get("amount", 0)
    currency = data.get("currency", "COP")
    description = data.get("description", "")
    projected_date = format_date(data.get("projected_date"))
    approved_at = format_date(data.get("approved_at"))
    approver_name = data.get("approver_name", "")
    provider_name = data.get("provider_name", "")
    company_name = data.get("company_name", "")

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px;">
      <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">

        <div style="background-color: #1a1a2e; padding: 24px; text-align: center;">
          <h1 style="color: #ffffff; margin: 0; font-size: 22px;">{company_name or 'Induretros'}</h1>
        </div>

        <div style="padding: 32px 24px;">
          <h2 style="color: #333; margin-top: 0;">Hola, {creator_name}</h2>
          <p style="color: #555; font-size: 16px; line-height: 1.6;">
            Tu pago ha sido <strong style="color: #27ae60;">aprobado</strong> por <strong>{approver_name}</strong>.
          </p>

          <div style="background-color: #f8f9fa; border-radius: 6px; padding: 20px; margin: 24px 0;">
            <table style="width: 100%; border-collapse: collapse;">
              <tr>
                <td style="padding: 10px 0; color: #777; font-size: 14px;">Descripcion</td>
                <td style="padding: 10px 0; text-align: right; font-size: 14px; color: #333; font-weight: 500;">
                  {description}
                </td>
              </tr>
              <tr style="border-top: 1px solid #eee;">
                <td style="padding: 10px 0; color: #777; font-size: 14px;">Monto</td>
                <td style="padding: 10px 0; text-align: right; font-size: 20px; font-weight: bold; color: #333;">
                  {format_currency(amount, currency)}
                </td>
              </tr>
              <tr style="border-top: 1px solid #eee;">
                <td style="padding: 10px 0; color: #777; font-size: 14px;">Proveedor</td>
                <td style="padding: 10px 0; text-align: right; font-size: 14px; color: #333;">
                  {provider_name}
                </td>
              </tr>
              <tr style="border-top: 1px solid #eee;">
                <td style="padding: 10px 0; color: #777; font-size: 14px;">Fecha proyectada</td>
                <td style="padding: 10px 0; text-align: right; font-size: 14px; color: #333;">
                  {projected_date}
                </td>
              </tr>
              <tr style="border-top: 1px solid #eee;">
                <td style="padding: 10px 0; color: #777; font-size: 14px;">Aprobado el</td>
                <td style="padding: 10px 0; text-align: right; font-size: 14px; color: #333;">
                  {approved_at}
                </td>
              </tr>
              <tr style="border-top: 1px solid #eee;">
                <td style="padding: 10px 0; color: #777; font-size: 14px;">Estado</td>
                <td style="padding: 10px 0; text-align: right; font-size: 14px; color: #27ae60; font-weight: bold;">
                  APROBADO
                </td>
              </tr>
            </table>
          </div>

          <p style="color: #555; font-size: 14px; line-height: 1.6;">
            Si tienes alguna pregunta sobre este pago, contacta al area administrativa.
          </p>
        </div>

        <div style="background-color: #f8f9fa; padding: 16px 24px; text-align: center;">
          <p style="color: #999; font-size: 12px; margin: 0;">
            &copy; {company_name or 'Induretros'} &mdash; Este es un correo automatico, por favor no respondas a este mensaje.
          </p>
        </div>

      </div>
    </body>
    </html>
    """


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/send-payment-notification", methods=["POST"])
@require_api_key
def send_payment_notification():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Se requiere un cuerpo JSON"}), 400

    required_fields = ["creator_email", "creator_name", "amount"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return jsonify({"error": f"Campos requeridos faltantes: {', '.join(missing)}"}), 400

    creator_email = data["creator_email"]
    company = data.get("company_name", "Induretros")

    try:
        send_email(
            to_email=creator_email,
            subject=f"Tu pago ha sido aprobado - {company}",
            html_body=build_payment_email_html(data),
        )
        return jsonify({"message": f"Notificacion enviada a {creator_email}"}), 200

    except Exception as e:
        return jsonify({"error": f"Error al enviar correo: {str(e)}"}), 500


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
