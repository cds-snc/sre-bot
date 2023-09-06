import React, {} from 'react';

export default function HomePage() {
    const BACKEND_URL = process.env.BACKEND_URL

    const googleLogout = () => {
        var logout_url= BACKEND_URL + "logout"
        window.location.href = logout_url 
      }
    return (
        <section>
            <h1> This is going to be the dashboard of the SRE bot</h1>
            <br></br>
            <button onClick={googleLogout} className="btn btn-xs sm:btn-sm md:btn-md lg:btn-lg border-zinc-950">Logout from Google</button>
    </section>
    );
}