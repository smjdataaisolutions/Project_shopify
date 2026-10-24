import { proxyAnalyticsRequest } from "../services/backend-proxy.server";
import { authenticate } from "../shopify.server";

export const loader = async ({ request }) => {
  return proxyAnalyticsRequest({
    request,
    authenticateAdmin: authenticate.admin,
  });
};

export const action = async ({ request }) => {
  return proxyAnalyticsRequest({
    request,
    authenticateAdmin: authenticate.admin,
  });
};
