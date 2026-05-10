import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

function hasRecoveryMarker(search: string, hash: string): boolean {
  const normalizedSearch = search.startsWith("?") ? search.slice(1) : search;
  const normalizedHash = hash.startsWith("#") ? hash.slice(1) : hash;

  const searchParams = new URLSearchParams(normalizedSearch);
  const hashParams = new URLSearchParams(normalizedHash);

  return (
    searchParams.get("type")?.toLowerCase() === "recovery" ||
    hashParams.get("type")?.toLowerCase() === "recovery" ||
    /type=recovery/i.test(normalizedSearch) ||
    /type=recovery/i.test(normalizedHash) ||
    /recovery/i.test(normalizedSearch) ||
    /recovery/i.test(normalizedHash)
  );
}

export function AuthRecoveryRedirector() {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (location.pathname === "/reset-password") return;
    if (!hasRecoveryMarker(location.search, location.hash)) return;

    navigate(
      {
        pathname: "/reset-password",
        search: location.search,
        hash: location.hash,
      },
      { replace: true },
    );
  }, [location.hash, location.pathname, location.search, navigate]);

  return null;
}
