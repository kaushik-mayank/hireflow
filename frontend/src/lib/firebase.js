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
 * True only when the REACT_APP_FIREBASE_* build-time vars are present.
 *
 * IMPORTANT: Create React App only inlines variables prefixed REACT_APP_.
 * Setting bare Firebase keys (apiKey, authDomain, projectId, ...) on the host
 * does NOT work — they are invisible to the built bundle, this stays false, and
 * the app silently used the legacy password path. That was the root cause of
 * the "signup bypasses Firebase" report. The warning below makes a repeat of
 * that misconfiguration loud instead of silent.
 */
export const isFirebaseConfigured = Boolean(
  firebaseConfig.apiKey && firebaseConfig.authDomain && firebaseConfig.projectId
);

/**
 * Escape hatch for local development only: set REACT_APP_ALLOW_PASSWORD_FALLBACK
 * =true to allow the legacy email+password path when Firebase is not
 * configured. In production leave this unset so a Firebase misconfiguration
 * fails visibly at signup rather than silently creating a weaker account.
 */
export const allowPasswordFallback =
  String(process.env.REACT_APP_ALLOW_PASSWORD_FALLBACK).toLowerCase() === "true";

if (!isFirebaseConfigured && typeof console !== "undefined") {
  // eslint-disable-next-line no-console
  console.error(
    "[HireFlow] Firebase is NOT configured. Expected REACT_APP_FIREBASE_API_KEY, " +
      "REACT_APP_FIREBASE_AUTH_DOMAIN and REACT_APP_FIREBASE_PROJECT_ID at build time. " +
      "Bare names like apiKey/authDomain/projectId are ignored by Create React App. " +
      (allowPasswordFallback
        ? "Legacy password auth is enabled (REACT_APP_ALLOW_PASSWORD_FALLBACK=true)."
        : "Sign-up is disabled until this is fixed.")
  );
}

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

/**
 * Sign in with email + password and enforce email verification.
 *
 * @returns {Promise<{emailVerified: boolean, idToken: string|null}>}
 *   When the email is not yet verified a fresh verification link is sent, the
 *   Firebase session is cleared, and idToken is null so the caller shows the
 *   "verify your email" state instead of proceeding to the dashboard.
 */
export async function firebaseSignIn(email, password) {
  const auth = await getAuthInstance();
  const { signInWithEmailAndPassword, sendEmailVerification, signOut } = await import("firebase/auth");
  const cred = await signInWithEmailAndPassword(auth, email, password);

  // Pull the latest account state from Firebase before checking verification.
  // Right after a user clicks the verification link, `emailVerified` on the
  // signed-in user object can still be stale (false); reload() fetches the
  // current server state so a just-verified user isn't wrongly blocked.
  try { await cred.user.reload(); } catch { /* non-fatal — fall back to the current value */ }

  if (!cred.user.emailVerified) {
    try { await sendEmailVerification(cred.user); } catch { /* non-fatal */ }
    try { await signOut(auth); } catch { /* non-fatal */ }
    return { emailVerified: false, idToken: null };
  }

  // Force a fresh ID token so the backend's email_verified claim is current
  // too — a cached token would still carry email_verified: false and the
  // backend would reject an otherwise-verified user.
  const idToken = await cred.user.getIdToken(true);
  return { emailVerified: true, idToken };
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
