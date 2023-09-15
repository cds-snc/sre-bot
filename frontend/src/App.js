import { ColorModeContext, useMode } from "./theme";
import { CssBaseline, ThemeProvider } from "@mui/material";
import { Routes, Route } from "react-router-dom";
import Topbar from "./scenes/global/Topbar";
import Dashboard from "./scenes/dashboard";
import Sidebar from "./scenes/global/Sidebar";
// import Team from "./scenes/team";
// import Invoices from "./scenes/invoices";
// import Contacts from "./scenes/contacts";
// import Bar from "./scenes/dashboard";
// import Form from "./scenes/form";
// import Line from "./scenes/line";
// import Pie from "./scenes/pie";
// import FAQ from "./scenes/faq";
// import Geography from "./scenes/geography";
// import Calendar from "./scenes/calendar/calendar";

function App() {

  // get the theme and the color mode
  const [theme, colorMode] = useMode();
  return (
    <ColorModeContext.Provider value={colorMode}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <div className = "app">
          <Sidebar />
          <main className="content">
            <Topbar />
            <Routes>
              <Route path="/" element={<Dashboard />} />
              {/* <Route path="/team" element={<Team/>} />
              <Route path="/contacts" element={<Contacts/>} />
              <Route path="/invoices" element={<Invoices/>} />
              <Route path="/form" element={<Form/>} />
              <Route path="/bar" element={<Bar/>} />
              <Route path="/pie" element={<Pie />} />
              <Route path="/line" element={<Line />} />
              <Route path="/faq" element={<FAQ />} />
              <Route path="/calendar" element={<Calendar />} />
              <Route path="/geography" element={<Geography />} /> */}
            </Routes>
          </main>
        </div>
        {/* <Dashboard /> */}
      </ThemeProvider>
    </ColorModeContext.Provider>
  ) 
}

export default App;
// import sre_bot_logo from './sre_bot_logo.png';

// import React, { Component } from 'react';
// import LandingPage from './pages/LandingPage.js';
// import HomePage from './pages/HomePage.js';
// import Dashboard from './components/Dashboard';

// // function App() {
// //   return (
// //   <div className="hero min-h-screen bg-base-200">
      
// //   <div className="hero-content flex-col lg:flex-row">
    
// //     <img src = {sre_bot_logo} alt="sre_bot"></img>
// //     <div>
// //       <Dashboard />
// //       {/* <BrowserRouter>
// //           <Routes>
// //             {/* <Route path="/" element={<LandingPage/>} /> */}
// //             {/* <Route path="/home" element={<HomePage/>} /> */}
// //             {/* <Route path="/" element={<Dashboard/>} />
// //           </Routes>
// //        </BrowserRouter> */}
// //     </div>
// //   </div>
// // </div>
// //   );
// // }

// const App = () => <Dashboard />;

// export default App;