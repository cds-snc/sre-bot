import { CssBaseline, ThemeProvider } from "@mui/material";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ColorModeContext, useMode } from "./theme";
import { React, useState, useEffect } from "react";
import LandingPage from './pages/LandingPage.js';
import Topbar from "./scenes/global/Topbar";
import Dashboard from "./scenes/dashboard";
import Sidebar from "./scenes/global/Sidebar";
import Webhooks from './scenes/webhooks';
import Incident from './scenes/incident';
import IncidentHistory from './scenes/incident_history';
import Geolocate from './scenes/geolocate';
import Faq from './scenes/faq';

function App() {
    const [theme, colorMode] = useMode();
    const [isSidebar, setIsSidebar] = useState(true);

    const useUserData = () => {
      const [userData, setUserData] = useState(null);

      console.log("In user data")
      useEffect(() => {
        // Make a GET request to the "/user" endpoint
        fetch('/user')
          .then(response => {
            // Check if the response status code is OK (200)
            if (!response.ok) {
              throw new Error('Network response was not ok');
            }
            // Parse the JSON response
            return response.json();
          })
          .then(data => {
            // Handle the JSON data from the response
            setUserData(data);
          })
          .catch(error => {
            console.error('There was a problem with the fetch operation:', error);
          });
      }, []);

      if (userData && userData.error === "Not logged in") {
        return false;
      }
      return true;
    };

    const isAuthenticated = useUserData();
    
    return (
      <BrowserRouter>
        <Routes>
          {isAuthenticated ? (
            <>
              <Route path="/" element={
                <ColorModeContext.Provider value={colorMode}>
                  <ThemeProvider theme={theme}>
                    <CssBaseline />
                    <div className="app">
                      <Sidebar isSidebar={isSidebar} />
                      <main className="content">
                        <Topbar setIsSidebar={setIsSidebar} />
                        <Dashboard/>
                      </main>
                    </div>
                  </ThemeProvider>
                </ColorModeContext.Provider>
              } />
              <Route path="/webhooks" element={
              <ColorModeContext.Provider value={colorMode}>
                  <ThemeProvider theme={theme}>
                    <CssBaseline />
                    <div className="app">
                      <Sidebar isSidebar={isSidebar} />
                      <main className="content">
                        <Topbar setIsSidebar={setIsSidebar} />
                        <Webhooks/>
                      </main>
                    </div>
                  </ThemeProvider>
                </ColorModeContext.Provider>} />
              <Route path="/incident" element={
              <ColorModeContext.Provider value={colorMode}>
                  <ThemeProvider theme={theme}>
                    <CssBaseline />
                    <div className="app">
                      <Sidebar isSidebar={isSidebar} />
                      <main className="content">
                        <Topbar setIsSidebar={setIsSidebar} />
                        <Incident/>
                      </main>
                    </div>
                  </ThemeProvider>
                </ColorModeContext.Provider>} />
                <Route path="/incident_history" element={
              <ColorModeContext.Provider value={colorMode}>
                  <ThemeProvider theme={theme}>
                    <CssBaseline />
                    <div className="app">
                      <Sidebar isSidebar={isSidebar} />
                      <main className="content">
                        <Topbar setIsSidebar={setIsSidebar} />
                        <IncidentHistory/>
                      </main>
                    </div>
                  </ThemeProvider>
                </ColorModeContext.Provider>} />
                <Route path="/geolocate" element={
              <ColorModeContext.Provider value={colorMode}>
                  <ThemeProvider theme={theme}>
                    <CssBaseline />
                    <div className="app">
                      <Sidebar isSidebar={isSidebar} />
                      <main className="content">
                        <Topbar setIsSidebar={setIsSidebar} />
                        <Geolocate/>
                      </main>
                    </div>
                  </ThemeProvider>
                </ColorModeContext.Provider>} />
                <Route path="/faq" element={
              <ColorModeContext.Provider value={colorMode}>
                  <ThemeProvider theme={theme}>
                    <CssBaseline />
                    <div className="app">
                      <Sidebar isSidebar={isSidebar} />
                      <main className="content">
                        <Topbar setIsSidebar={setIsSidebar} />
                        <Faq/>
                      </main>
                    </div>
                  </ThemeProvider>
                </ColorModeContext.Provider>} />
              <Route path="/logout" element = {<LandingPage/>} />
            </>
          ) : (
            <Route path="/" element={<LandingPage />} />
          )}
        </Routes>
      </BrowserRouter>
    );
   }
  export default App;