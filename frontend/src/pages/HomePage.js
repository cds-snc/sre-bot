import React from "react";
import { useUser } from "../context/UserProvider";

export default function HomePage() {
  const { userData, isAuthenticated } = useUser();

  const googleLogout = () => {
    const isDevelopment = process.env.NODE_ENV === "development";
    const logoutUrl = isDevelopment
      ? "http://127.0.0.1:8000/logout"
      : "/logout";

    fetch(logoutUrl, {
      method: "GET",
      // credentials: "include", // Include cookies in the request
    })
      .then(() => {
        // Redirect the user to the root of the app
        window.location.href = "/";
      })
      .catch((error) => {
        console.error("Error during logout:", error);
      });
  };

  return (
    <div>
      {isAuthenticated ? (
        <div>
          <h1 className="text-5xl font-bold">Welcome {userData.name}!</h1>
          <br></br>
          <p>
            This is the SRE Bot frontend dashboard. To log out, press the logout
            button.
          </p>
          <br></br>
          <button
            onClick={googleLogout}
            className="btn btn-xs sm:btn-sm md:btn-md lg:btn-lg border-zinc-950"
          >
            Logout from Google
          </button>
        </div>
      ) : (
        <p>Error: Not logged in</p>
      )}
    </div>
  );
}
