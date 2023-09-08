import React, {} from 'react';

export default function HomePage() {
        const REACT_APP_BACKEND_URL = "http://127.0.0.1:8000/"//process.env.BACKEND_URL

        const googleLogout = () => {
                var logout_url= REACT_APP_BACKEND_URL + "logout"
                window.location.href = logout_url 
            }

            const temp = () =>{
                return fetch('http://127.0.0.1:8000/user')
                .then((response) => {
                    return response.json();
                })
                .then((myJson) => {
                    return myJson;
                });
            }
            console.log(temp().then(data => data))
            console.log(temp)

        return (
                <section>
                        <h1> {temp().then(data => data)} is going to be the dashboard of the SRE bot</h1>
                        <br></br>
                        <button onClick={googleLogout} className="btn btn-xs sm:btn-sm md:btn-md lg:btn-lg border-zinc-950">Logout from Google</button>
        </section>
        );
}