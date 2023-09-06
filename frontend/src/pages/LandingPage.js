import React, {} from 'react';
import {Link} from 'react-router-dom';

export default function HomePage() {
    return (
        <div>
            <Link to="/login"><kbd className="kbd kbd-lg">Login</kbd></Link>
        </div>
    );
}
