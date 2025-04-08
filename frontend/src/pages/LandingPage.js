import React, {} from 'react';
import sre_bot_logo from '../static/sre_bot_logo.png';

// Landing page. This is the initial screen that the user sees when they visit the site, prompting them to log in. 
// You can login with a google account tied only to the organization

export default function LoginPage() {

  // Google login function to handling logging in.
    const googleLogin = () => {
      const isDevelopment = process.env.NODE_ENV === "development";
      const loginUrl = isDevelopment
        ? "http://localhost:8000/login"
        : "/login";
        console.log("Redirecting to:", loginUrl);
        window.location.href = loginUrl;
      }
    return (
      <div className="hero min-h-screen bg-base-200">
      
      <div className="hero-content flex-col lg:flex-row">
    
     <img src = {sre_bot_logo} alt="sre_bot"></img>
   <div>
     <section>
      <div>
      <h1 className="text-5xl font-bold">Welcome!</h1>
      <br></br>
      <p>Log into the SRE bot by pressing the button below</p>
      <br></br>
      <button onClick={googleLogin} className="btn btn-xs sm:btn-sm md:btn-md lg:btn-lg border-zinc-950">Login with Google</button>
      </div>
    </section>
    </div>
  </div>
</div>
);
}
