import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

/* Note: this previously mounted a @tanstack/react-query QueryClientProvider.
   Nothing in the app ever called a react-query hook — fetching is done with
   axios inside useEffect — so the whole library was bundled to provide a
   context with no consumers. Removed. If react-query is adopted later, mount
   the provider again at that point. */

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
