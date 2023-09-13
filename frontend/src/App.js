import sre_bot_logo from './sre_bot_logo.png';
import './App.css';
import sre_bot_logo from './sre_bot_logo.png';


import {BrowserRouter, Routes, Route} from 'react-router-dom';
import LandingPage from './pages/LandingPage.js';
import HomePage from './pages/HomePage.js';

function App() {
  return (
  <div className="hero min-h-screen bg-base-200">
      
  <div className="hero-content flex-col lg:flex-row">
    
    <img src = {sre_bot_logo} alt="sre_bot"></img>
    <div>
      {/* <h1 className="text-5xl font-bold">Welcome!</h1> */}
      {/* <p className="py-6">This is the UI for the SRE bot.</p> */}
      <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingPage/>} />
            <Route path="/home" element={<HomePage/>} />
          </Routes>
       </BrowserRouter>
    </div>
  </div>
</div>
  );
}

export default App;
