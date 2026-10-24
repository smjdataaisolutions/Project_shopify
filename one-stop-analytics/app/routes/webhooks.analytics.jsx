import { forwardAnalyticsWebhook } from "../services/shopify-webhook-proxy.server";
import { authenticate } from "../shopify.server";

export const action = async ({ request }) => {
  return forwardAnalyticsWebhook({
    request,
    authenticateWebhook: authenticate.webhook,
  });
};
