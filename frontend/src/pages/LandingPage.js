import React, {} from 'react';

export default function LoginPage() {

    const googleLogin = () => {
        var login_url = "/login"
        console.log("login_url", login_url)
        window.location.href = login_url
      }
    return (
     <section>
      <div>
      <h1 className="text-5xl font-bold">Welcome!</h1>
      <br></br>
      <p>Log into the SRE bot by pressing the button below</p>
      <br></br>
      <button onClick={googleLogin} className="btn btn-xs sm:btn-sm md:btn-md lg:btn-lg border-zinc-950">Login with Google</button>
      </div>
    </section>
    );
}
