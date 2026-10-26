import { GoogleAuth } from "google-auth-library";

let googleAuth;
const clientPromises = new Map();

function getGoogleAuth() {
  googleAuth ??= new GoogleAuth();
  return googleAuth;
}

export async function getGoogleIdentityToken(audience) {
  let clientPromise = clientPromises.get(audience);
  if (!clientPromise) {
    clientPromise = getGoogleAuth().getIdTokenClient(audience);
    clientPromises.set(audience, clientPromise);
  }

  const client = await clientPromise;
  return client.idTokenProvider.fetchIdToken(audience);
}
