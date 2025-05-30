import { CssBaseline, ThemeProvider } from "@mui/material";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ColorModeContext, useMode } from "./theme";
import { React, useState } from "react";
import { useUser } from "./context/UserProvider";
import LandingPage from "./pages/LandingPage.js";
import Topmenu from "./scenes/global/Topmenu";
import Dashboard from "./scenes/dashboard";
import Version from "./scenes/version";
import AwsAccessManager from "./scenes/access";
import Sidemenu from "./scenes/global/Sidemenu";
import Webhooks from "./scenes/webhooks";
import Incident from "./scenes/incident";
import IncidentHistory from "./scenes/incident_history";
import Geolocate from "./scenes/geolocate";
import Faq from "./scenes/faq";
import Logout from "./scenes/logout";

/**
 * The main component of the application.
 */
function App() {
  // Get the current theme and color mode
  const [theme, colorMode] = useMode();

  // Set the initial state of the Sidemenu
  const [isSidemenu, setIsSidemenu] = useState(true);

  const { isAuthenticated } = useUser();

  // if we are initially loading the page and isAuthenticated is null, return null. This fixes a flashing issue.
  if (isAuthenticated === null) {
    return null;
  }

  // Render the application. If the user is authenticated, show the Sidemenu, Topmenu and menu items.
  // Otherwise (ie user is not logged in), show the landing page where an user can log in.
  return (
    <BrowserRouter>
      <Routes>
        {isAuthenticated ? (
          <>
            <Route
              path="/"
              element={
                <ColorModeContext.Provider value={colorMode}>
                  <ThemeProvider theme={theme}>
                    <CssBaseline />
                    <div className="app">
                      <Sidemenu isSidemenu={isSidemenu} />
                      <main className="content">
                        <Topmenu setIsSidemenu={setIsSidemenu} />
                        <Dashboard />
                      </main>
                    </div>
                  </ThemeProvider>
                </ColorModeContext.Provider>
              }
            />
            <Route
              path="/webhooks"
              element={
                <ColorModeContext.Provider value={colorMode}>
                  <ThemeProvider theme={theme}>
                    <CssBaseline />
                    <div className="app">
                      <Sidemenu isSidemenu={isSidemenu} />
                      <main className="content">
                        <Topmenu setIsSidemenu={setIsSidemenu} />
                        <Webhooks />
                      </main>
                    </div>
                  </ThemeProvider>
                </ColorModeContext.Provider>
              }
            />
            <Route
              path="/access"
              element={
                <ColorModeContext.Provider value={colorMode}>
                  <ThemeProvider theme={theme}>
                    <CssBaseline />
                    <div className="app">
                      <Sidemenu isSidemenu={isSidemenu} />
                      <main className="content">
                        <Topmenu setIsSidemenu={setIsSidemenu} />
                        <AwsAccessManager />
                      </main>
                    </div>
                  </ThemeProvider>
                </ColorModeContext.Provider>
              }
            />
            <Route
              path="/incident"
              element={
                <ColorModeContext.Provider value={colorMode}>
                  <ThemeProvider theme={theme}>
                    <CssBaseline />
                    <div className="app">
                      <Sidemenu isSidemenu={isSidemenu} />
                      <main className="content">
                        <Topmenu setIsSidemenu={setIsSidemenu} />
                        <Incident />
                      </main>
                    </div>
                  </ThemeProvider>
                </ColorModeContext.Provider>
              }
            />
            <Route
              path="/incident_history"
              element={
                <ColorModeContext.Provider value={colorMode}>
                  <ThemeProvider theme={theme}>
                    <CssBaseline />
                    <div className="app">
                      <Sidemenu isSidemenu={isSidemenu} />
                      <main className="content">
                        <Topmenu setIsSidemenu={setIsSidemenu} />
                        <IncidentHistory />
                      </main>
                    </div>
                  </ThemeProvider>
                </ColorModeContext.Provider>
              }
            />
            <Route
              path="/geolocate"
              element={
                <ColorModeContext.Provider value={colorMode}>
                  <ThemeProvider theme={theme}>
                    <CssBaseline />
                    <div className="app">
                      <Sidemenu isSidemenu={isSidemenu} />
                      <main className="content">
                        <Topmenu setIsSidemenu={setIsSidemenu} />
                        <Geolocate />
                      </main>
                    </div>
                  </ThemeProvider>
                </ColorModeContext.Provider>
              }
            />
            <Route
              path="/faq"
              element={
                <ColorModeContext.Provider value={colorMode}>
                  <ThemeProvider theme={theme}>
                    <CssBaseline />
                    <div className="app">
                      <Sidemenu isSidemenu={isSidemenu} />
                      <main className="content">
                        <Topmenu setIsSidemenu={setIsSidemenu} />
                        <Faq />
                      </main>
                    </div>
                  </ThemeProvider>
                </ColorModeContext.Provider>
              }
            />
            <Route
              path="/version"
              element={
                <ColorModeContext.Provider value={colorMode}>
                  <ThemeProvider theme={theme}>
                    <CssBaseline />
                    <div className="app">
                      <Sidemenu isSidemenu={isSidemenu} />
                      <main className="content">
                        <Topmenu setIsSidemenu={setIsSidemenu} />
                        <Version />
                      </main>
                    </div>
                  </ThemeProvider>
                </ColorModeContext.Provider>
              }
            />
            <Route path="/logout" element={<Logout />} />
          </>
        ) : (
          <Route path="/" element={<LandingPage />} />
        )}
      </Routes>
    </BrowserRouter>
  );
}

export default App;
