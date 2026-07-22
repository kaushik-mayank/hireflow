import { createContext, useContext, useState, useEffect, useCallback, useMemo } from "react";
import { authApi } from "@/api";
import { firebaseSignOut } from "@/lib/firebase";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem("hireflow_token"));
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    const t = localStorage.getItem("hireflow_token");
    if (!t) {
      setLoading(false);
      return;
    }
    try {
      const res = await authApi.me();
      setUser(res.data.user);
    } catch {
      localStorage.removeItem("hireflow_token");
      setToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = useCallback((tok, usr) => {
    localStorage.setItem("hireflow_token", tok);
    setToken(tok);
    setUser(usr);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("hireflow_token");
    setToken(null);
    setUser(null);
    // Clear the Firebase session too, otherwise the browser stays signed in to
    // Firebase and the next sign-in silently reuses the old identity.
    firebaseSignOut();
  }, []);

  /* Memoised because this object is consumed by every screen in the app. As a
     fresh literal it changed identity on each render of AuthProvider, forcing
     every consumer to re-render even when nothing about the session moved. */
  const value = useMemo(
    () => ({ user, token, loading, login, logout }),
    [user, token, loading, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
