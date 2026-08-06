import { boundary } from "@shopify/shopify-app-react-router/server";
import { AnalyticsTopNavigation } from "../components/navigation/AnalyticsTopNavigation";
import { authenticate } from "../shopify.server";

export const loader = async ({ request }) => {
  await authenticate.admin(request);
  return null;
};

export default function Products() {
  return (
    <s-page heading="Products">
      <AnalyticsTopNavigation />

      <s-section>
        <s-text>Coming soon</s-text>
      </s-section>
    </s-page>
  );
}

export const headers = (headersArgs) => boundary.headers(headersArgs);
