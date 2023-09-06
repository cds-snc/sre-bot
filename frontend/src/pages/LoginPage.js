import React, {} from "react";

import axios from "axios";
import {useNavigate} from "react-router-dom";

export default function LoginPage() {
    const navigate = useNavigate();

    axios.post("http://127.0.0.1:8000/login", {}).then((response) => { console.log(response); navigate("/");
    }).catch((error) => { console.log(error); })
    return (
        <div>
            <h1>Login Page</h1>
        </div>
    );
}