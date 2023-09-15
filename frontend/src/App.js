import Topbar from "./scenes/global/Topbar";
import { ColorModeContext, useMode } from "./theme";
import { CssBaseline, ThemeProvider } from "@mui/material";

function App() {

  // get the theme and the color mode
  const [theme, colorMode] = useMode();
  return (
    <ColorModeContext.Provider value={colorMode}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <div className = "app">
          <main className="content">
            <Topbar />
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