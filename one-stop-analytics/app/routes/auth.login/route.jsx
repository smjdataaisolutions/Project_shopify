import { AppProvider } from "@shopify/shopify-app-react-router/react";
import { useLoaderData } from "react-router";
import { login } from "../../shopify.server";
import { loginErrorMessage } from "./error.server";

export const loader = async ({ request }) => {
  const errors = loginErrorMessage(await login(request));

  return { errors };
};

export default function Auth() {
  const { errors } = useLoaderData();

  return (
    <AppProvider embedded={false}>
      <s-page>
        <s-section heading="Install OneStop Analytics from Shopify">
          <s-stack direction="block" gap="base">
            <s-text>
              OneStop Analytics can only be installed or opened from a
              Shopify-owned surface.
            </s-text>
            <s-text tone="subdued">
              Open the app from your Shopify Admin or its Shopify App Store
              listing to continue securely.
            </s-text>
            {errors?.shop ? (
              <s-banner tone="critical">
                Shopify could not verify the installation request. Return to
                Shopify Admin and open OneStop Analytics again.
              </s-banner>
            ) : null}
          </s-stack>
        </s-section>
      </s-page>
    </AppProvider>
  );
}
