// =============================================================================
// Supabase Edge Function: notify-payment-approved
// =============================================================================
// Se invoca desde el frontend de Lovable cuando un admin aprueba un pago.
// Recibe todos los datos del pago en el body y los reenvia al servidor Flask.
//
// INSTRUCCIONES DE DESPLIEGUE:
// 1. Instala Supabase CLI: npm install -g supabase
// 2. Vincula tu proyecto: supabase link --project-ref TU_PROJECT_REF
// 3. Crea la funcion: supabase functions new notify-payment-approved
// 4. Copia este archivo a supabase/functions/notify-payment-approved/index.ts
// 5. Configura los secretos:
//    supabase secrets set FLASK_API_URL=<tu-url-del-servidor>
//    supabase secrets set FLASK_API_KEY=<tu-api-key>
// 6. Despliega: supabase functions deploy notify-payment-approved
// =============================================================================

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    // El frontend envia todos los datos del pago directamente
    const paymentData = await req.json();

    // Validar campos minimos
    const required = ["creator_email", "creator_name", "amount"];
    const missing = required.filter((f) => !paymentData[f]);
    if (missing.length > 0) {
      return new Response(
        JSON.stringify({ error: `Campos requeridos faltantes: ${missing.join(", ")}` }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Reenviar al servidor Flask
    const flaskApiUrl = Deno.env.get("FLASK_API_URL")!;
    const flaskApiKey = Deno.env.get("FLASK_API_KEY")!;

    const response = await fetch(
      `${flaskApiUrl}/api/send-payment-notification`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": flaskApiKey,
        },
        body: JSON.stringify(paymentData),
      }
    );

    const result = await response.json();

    if (!response.ok) {
      return new Response(
        JSON.stringify({ error: "Error enviando notificacion", details: result }),
        { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    return new Response(
      JSON.stringify({ message: "Notificacion enviada exitosamente", details: result }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (error) {
    return new Response(
      JSON.stringify({ error: "Error interno", details: error.message }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
