import { forwardComplianceWebhook } from "../services/shopify-webhook-proxy.server";
import { authenticate } from "../shopify.server";
import db from "../db.server";

export const action = async ({ request }) => {
  let authenticatedShop;
  const response = await forwardComplianceWebhook({
    request,
    authenticateWebhook: async (webhookRequest) => {
      const authentication = await authenticate.webhook(webhookRequest);
      authenticatedShop = authentication.shop;
      return authentication;
    },
  });

  if (
    response.ok &&
    authenticatedShop &&
    request.headers.get("x-shopify-topic")?.toLowerCase() === "shop/redact"
  ) {
    await db.session.deleteMany({ where: { shop: authenticatedShop } });
  }

  return response;
};
