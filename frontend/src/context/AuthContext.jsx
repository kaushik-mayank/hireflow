import { createContext, useContext, useState, useEffect, useCallback } from "react";
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

  const login = (tok, usr) => {
    localStorage.setItem("hireflow_token", tok);
    setToken(tok);
    setUser(usr);
  };

  const logout = () => {
    localStorage.removeItem("hireflow_token");
    setToken(null);
    setUser(null);
    // Clear the Firebase session too, otherwise the browser stays signed in to
    // Firebase and the next sign-in silently reuses the old identity.
    firebaseSignOut();
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
