import React, { createContext, useContext, useState, useEffect } from "react";

const UserContext = createContext();

export const UserProvider = ({ children }) => {
  const [userData, setUserData] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(null);

  useEffect(() => {
    const isDevelopment = process.env.NODE_ENV === "development";
    const userUrl = isDevelopment
      ? "http://127.0.0.1:8000/auth/me" // Backend URL in development
      : "/auth/me"; // Relative URL in production

    const fetchUserData = async () => {
      try {
        const response = await fetch(userUrl, {
          credentials: "include", // Include cookies for session handling
        });
        if (!response.ok) {
          throw new Error("Network response was not ok");
        }
        const data = await response.json();
        setUserData(data);
        setIsAuthenticated(data.error !== "Not logged in");
      } catch (error) {
        console.error("Error fetching user data:", error);
        setIsAuthenticated(false);
      }
    };

    fetchUserData();
  }, []);

  return (
    <UserContext.Provider value={{ userData, isAuthenticated }}>
      {children}
    </UserContext.Provider>
  );
};

export const useUser = () => useContext(UserContext);