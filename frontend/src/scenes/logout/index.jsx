import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const Logout = () => {
    const navigate = useNavigate();
  
    useEffect(() => {
      const handleLogout = async () => {
        try {
          const response = await fetch(`${window.origin}/logout`, {
            method: 'GET',
            credentials: 'include', // Include credentials to manage session
          });
  
          if (response.ok) {
            // Clear the authentication state and redirect to the landing page
            window.location.reload(); // Refresh the session
          } else {
            console.error('Failed to log out');
          }
        } catch (error) {
          console.error('An error occurred during logout:', error);
        }
      };
  
      handleLogout();
    }, [navigate]);
  
    return null; // This component doesn't render anything
  };
  
  export default Logout;