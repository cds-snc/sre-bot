import React, {} from 'react';

export default function LoginPage() {
  const BACKEND_URL = process.env.BACKEND_URL

    const googleLogin = () => {
        var login_url = BACKEND_URL + "/login"
        console.log("login_url", login_url)
        window.location.href = login_url
      }
    return (
        <section>
      <div>
      <button onClick={googleLogin} className="btn btn-xs sm:btn-sm md:btn-md lg:btn-lg border-zinc-950">Login with Google</button>
      </div>
    </section>
    );
}
