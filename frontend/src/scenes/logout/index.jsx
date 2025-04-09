import React, { useEffect } from "react";

const Logout = () => {
  useEffect(() => {
    const handleLogout = async () => {
      const logoutUrl = "/auth/logout"; // Use relative URL to leverage the proxy

      try {
        const response = await fetch(logoutUrl, {
          method: "GET",
          credentials: "include", // Include cookies in the request
        });

        if (response.ok) {
          // Redirect the user to the root of the app
          window.location.href = "/";
        } else {
          console.error("Failed to log out");
        }
      } catch (error) {
        console.error("An error occurred during logout:", error);
      }
    };

    handleLogout();
  }, []);

  return null; // This component doesn't render anything
};

export default Logout;