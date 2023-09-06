import './App.css';

import {BrowserRouter, Routes, Route, Switch} from 'react-router-dom';
import React, { useState, useEffect } from 'react';

import LandingPage from './pages/LandingPage.js';
import LoginPage from './pages/LoginPage.js';

function App() {
  // fetch('/login').then(res => res.json())
  const [currentTime, setCurrentTime] = useState(0);

  // useEffect(() => {
  //   fetch('/login').then(res => res.json()).then(data => {
  //     setCurrentTime(data.time);
  //   });
  // }, []);
  return (
    <div className="hero min-h-screen bg-base-200">
  <div className="hero-content flex-col lg:flex-row">
    <img src="sre_bot_logo.png" className="max-w-sm rounded-lg shadow-2xl" alt="sre_bot"></img>
    <div>
      <h1 className="text-5xl font-bold">Welcome!</h1>
      <p className="py-6">This is the UI for the SRE bot.</p>
      <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingPage/>} />
            {/* <Route path="/login" element={<LoginPage/>} /> */}
          </Routes>
       </BrowserRouter>
    </div>
  </div>
</div>
    // <div className="container mx-auto bg-gray-200 rounded-xl shadow border p-8 m-10">
    //     <img src="sre_bot_logo.png" alt="sre_bot" style={{maxWidth: "10%"}}></img>
    //     <br></br>
    //         <p className="text-3xl text-gray-700 font-bold mb-5">
    //     Welcome to the SRE Bot!
    //   </p>
    //   <p className="text-gray-500 text-lg">
    //     To login, please click the button below. 
    //   </p>
    //   <br></br>
    //   <BrowserRouter>
    //      <Routes>
    //        <Route path="/" element={<LandingPage/>} />
    //        <Route path="/login" element={<LoginPage/>} />
    //      </Routes>
    //    </BrowserRouter>
    //  </div>

    // <div className="App">
    //   {/* <header className="App-header">
    //     <img src = "sre_bot_logo.png" alt="sre_bot"></img>
    //     <h1>SRE Bot Admin</h1>
    //   </header> */}
    //   <h1>Welcome to the SRE Bot Admin UI</h1>
    //   <p class="font-serif text-2xl">Please login to continue</p>

    //   <BrowserRouter>
    //     <Routes>
    //       <Route path="/" element={<LandingPage/>} />
    //       <Route path="/login" element={<LoginPage/>} />
    //     </Routes>
    //   </BrowserRouter>
    // </div>
  );
}

export default App;
