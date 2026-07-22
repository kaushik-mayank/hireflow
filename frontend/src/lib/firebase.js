/**
 * Firebase Authentication wrapper.
 *
 * This project is Create React App + CRACO, so environment variables are read
 * from `process.env.REACT_APP_*` and are inlined at BUILD time — they must be
 * set on the Render frontend service before the build runs, not at runtime.
 * (`import.meta.env.VITE_*` is Vite syntax and does not apply here.)
 *
 * The SDK is pulled in via dynamic import so it only downloads when someone
 * actually visits an auth page — it never lands in the dashboard bundle.
 *
 * Firebase owns credentials, email verification and password resets. It does
 * NOT own sessions: after sign-in we exchange the Firebase ID token for this
 * app's own JWT, so every existing route, guard and interceptor is untouched.
 */

const firebaseConfig = {
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY,
  authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID,
  storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.REACT_APP_FIREBASE_APP_ID,
  measurementId: process.env.REACT_APP_FIREBASE_MEASUREMENT_ID,
};

/**
 * When the config is absent (local dev without the env vars), the app falls
 * back to the legacy password endpoints instead of showing a broken screen.
 */
export const isFirebaseConfigured = Boolean(
  firebaseConfig.apiKey && firebaseConfig.authDomain && firebaseConfig.projectId
);

let authPromise = null;

async function getAuthInstance() {
  if (!isFirebaseConfigured) {
    throw new Error("Firebase is not configured");
  }
  if (!authPromise) {
    authPromise = (async () => {
      const { initializeApp, getApps, getApp } = await import("firebase/app");
      const { getAuth } = await import("firebase/auth");
      const app = getApps().length ? getApp() : initializeApp(firebaseConfig);

      // Analytics is optional and must never be able to break sign-in.
      if (firebaseConfig.measurementId) {
        import("firebase/analytics")
          .then(({ getAnalytics, isSupported }) =>
            isSupported().then((ok) => ok && getAnalytics(app))
          )
          .catch(() => {});
      }
      return getAuth(app);
    })();
  }
  return authPromise;
}

/** Firebase error codes that mean "no such account here" — worth retrying
 *  against the legacy password store, which still holds pre-Firebase users.
 *  Note: with email-enumeration protection enabled (the default on newer
 *  projects) a wrong password also surfaces as `invalid-credential`. */
const FALLBACK_CODES = new Set([
  "auth/user-not-found",
  "auth/invalid-credential",
  "auth/invalid-login-credentials",
  "auth/wrong-password",
]);

export function shouldTryLegacyLogin(err) {
  return FALLBACK_CODES.has(err?.code);
}

/** Raw Firebase codes are not user-facing. Map them to the app's voice. */
const MESSAGES = {
  "auth/invalid-email": "That email address doesn't look right.",
  "auth/missing-email": "Please enter your email address.",
  "auth/missing-password": "Please enter your password.",
  "auth/user-not-found": "We couldn't find an account with that email.",
  "auth/wrong-password": "That password isn't correct.",
  "auth/invalid-credential": "That email or password isn't correct.",
  "auth/invalid-login-credentials": "That email or password isn't correct.",
  "auth/email-already-in-use": "An account with this email already exists.",
  "auth/weak-password": "Please choose a password with at least 8 characters.",
  "auth/user-disabled": "This account has been disabled. Please contact support.",
  "auth/too-many-requests": "Too many attempts. Please wait a few minutes and try again.",
  "auth/network-request-failed": "Couldn't reach the sign-in service. Check your connection and try again.",
  "auth/operation-not-allowed": "Email and password sign-in isn't enabled for this project.",
  "auth/requires-recent-login": "Please sign in again to continue.",
};

export function firebaseErrorMessage(err, fallback = "Something went wrong. Please try again.") {
  return MESSAGES[err?.code] || fallback;
}

/**
 * Create the account and send a verification email.
 * @returns {Promise<string>} a Firebase ID token to exchange for an app JWT
 */
export async function firebaseSignUp(email, password) {
  const auth = await getAuthInstance();
  const { createUserWithEmailAndPassword, sendEmailVerification } = await import("firebase/auth");
  const cred = await createUserWithEmailAndPassword(auth, email, password);
  // A failed verification email must not block a successful signup.
  try {
    await sendEmailVerification(cred.user);
  } catch {
    /* ignore */
  }
  return cred.user.getIdToken();
}

/** @returns {Promise<string>} a Firebase ID token to exchange for an app JWT */
export async function firebaseSignIn(email, password) {
  const auth = await getAuthInstance();
  const { signInWithEmailAndPassword } = await import("firebase/auth");
  const cred = await signInWithEmailAndPassword(auth, email, password);
  return cred.user.getIdToken();
}

export async function firebaseSendPasswordReset(email) {
  const auth = await getAuthInstance();
  const { sendPasswordResetEmail } = await import("firebase/auth");
  await sendPasswordResetEmail(auth, email);
}

/** Clears the Firebase session. The app JWT is cleared separately by AuthContext. */
export async function firebaseSignOut() {
  if (!isFirebaseConfigured) return;
  try {
    const auth = await getAuthInstance();
    const { signOut } = await import("firebase/auth");
    await signOut(auth);
  } catch {
    /* a failed Firebase sign-out must not block local logout */
  }
}
