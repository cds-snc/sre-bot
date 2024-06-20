import Header from "../../components/Header";
import { Box } from "@mui/material";
import React, { useState, useEffect } from 'react';



// call the api to get the version 
const Version = () => {
    const [version, setVersion] = useState('');
    const [error, setError] = useState('');
  
    useEffect(() => {
      const fetchVersion = async () => {
        try {
          const response = await fetch(`${window.origin}/version`);
          if (!response.ok) {
            throw new Error('Network response was not ok');
          }
          const data = await response.json();
          setVersion(data.version);
        } catch (err) {
          setError('Failed to fetch version');
          console.error('Error fetching version:', err);
        }
      };
  
      fetchVersion();
    }, []);

    // format the subtitle content 
    const subtitleContent = error ? (
        `Error: ${error}`
      ) : (
        <>
          SRE Bot Version: <b>{version}</b>
        </>
      );

    //display the version
    return (
              <Box m="20px">
                <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Header title="Version" subtitle={subtitleContent} /> 
                </Box>
            </Box>
    );
 }

 export default Version;