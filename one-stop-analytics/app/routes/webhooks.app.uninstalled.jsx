import { authenticate } from "../shopify.server";
import db from "../db.server";
import { forwardAnalyticsWebhook } from "../services/shopify-webhook-proxy.server";

export const action = async ({ request }) => {
  const analyticsRequest = request.clone();
  const { shop, session, topic } = await authenticate.webhook(request);

  console.log(`Received ${topic} webhook for ${shop}`);

  // Webhook requests can trigger multiple times and after an app has already been uninstalled.
  // If this webhook already ran, the session may have been deleted previously.
  if (session) {
    await db.session.deleteMany({ where: { shop } });
  }

  return forwardAnalyticsWebhook({
    request: analyticsRequest,
    authenticateWebhook: async () => ({ shop }),
  });
};
