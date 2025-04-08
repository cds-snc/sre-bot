import React, { useEffect, useState } from "react";

export default function HomePage() {
  const [userData, setUserData] = useState(null);

  useEffect(() => {
    // Make a GET request to the "/user" endpoint
    fetch("/user")
      .then((response) => {
        // Check if the response status code is OK (200)
        if (!response.ok) {
          throw new Error("Network response was not ok");
        }
        // Parse the JSON response
        return response.json();
      })
      .then((data) => {
        // Handle the JSON data from the response
        setUserData(data);
      })
      .catch((error) => {
        console.error("There was a problem with the fetch operation:", error);
      });
  }, []);
  const googleLogout = () => {
    const isDevelopment = process.env.NODE_ENV === "development";
    const logoutUrl = isDevelopment
      ? "http://localhost:8000/logout"
      : "/logout";

    window.location.href = logoutUrl;
  };

  return (
    <div>
      {userData ? (
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
