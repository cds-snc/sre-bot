import { Box, Alert } from "@mui/material";
import Header from "../../components/Header";
import { React, useState } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps"
import { Marker } from "react-simple-maps"
import Paper from '@mui/material/Paper';
import InputBase from '@mui/material/InputBase';
import IconButton from '@mui/material/IconButton';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import SearchIcon from '@mui/icons-material/Search';
import PinDropIcon from '@mui/icons-material/PinDrop';

//set the maps' width and height cooordinates
const width = 800
const height = 500
const geoUrl =
  "https://raw.githubusercontent.com/deldersveld/topojson/master/world-countries.json"


// call the backend API to fetch the location data using the /geolocate endpoint
function fetchLocationData(inputValue) {
  console.log("ENVIRONMENT: " + process.env.ENVIRONMENT)
  if (process.env.ENVIRONMENT === 'dev') {
    console.log("In dev mode, using mock data")
    return fetch('https://sre-bot.cdssandbox.xyz/geolocate/');
  }
  else {
  return fetch('https://sre-bot.cdssandbox.xyz/geolocate/' + inputValue);
  }
}

function Geolocate() {
  const [inputValue, setInputValue] = useState('');
  const [location, setLocation] = useState(null);

  //execute the fetchLocationData function when the user clicks on the search button or presses enter
  function handleGeolocateSearch(e) {
    e.preventDefault();
    //call the api to fetch the location data
    fetchLocationData(inputValue).then(response => {
    if (!response.ok) {
      throw new Error('Invalid IP address');
    }
    return response.json();
    })
    .then(data => {
      // Handle the JSON data from the response
      setLocation(data);
    })
    .catch(error => {
      setLocation({detail: "Something went wrong: " + error});
      console.error('There was a problem with the fetch operation:', error);
    });
  };

  // execute the handleGeolocateSearch function when the user presses enter
  function HandleKeyDown(e) {
    if (e.key === 'Enter') {
      handleGeolocateSearch(e);
    }
  }
 
  return (
    <Box m="20px">
      {/* Display the title */}
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Header title="Geolocate an IP"/>
      </Box>
      {/* Display the input bo and search button */}
      <Box>
        <Paper
          sx={{ p: '2px 4px', display: 'flex', alignItems: 'center', width: 400 }}
        >
        <IconButton sx={{ p: '10px' }} aria-label="menu">
        <PinDropIcon/>
          {/* <MenuIcon /> */}
        </IconButton>
        <InputBase
          sx={{ ml: 1, flex: 1 }}
          placeholder="Enter an IP Address to geolocate"
          inputProps={{ 'aria-label': 'search ip' }}
          onChange={e => setInputValue(e.target.value)}
          onKeyDown={e => HandleKeyDown(e)}
          />
          <IconButton type="button" sx={{ p: '10px' }} aria-label="search" onClick={handleGeolocateSearch}>
            <SearchIcon />
          </IconButton>
        </Paper>
        {/* If we have data, then display the city, country and location coordinates. If not, then display the error alert */}
        {location && location.detail ? (
          <Box > 
        <Alert sx={{fontSize:'larger'}} severity="error">{location.detail}</Alert></Box> 
        ) : (
          location && <Box sx={{fontSize:'larger'}}><br></br><CheckCircleOutlineIcon color="success" fontSize="large"/>  Located in <b>{location.city}, {location.country}</b> with coordinates [{location.latitude}, {location.longitude}]</Box>)}
        {/* Display the map */}
        <ComposableMap width={width} height={height}>
          <Geographies geography={geoUrl}>
            {({ geographies }) =>
              geographies.map((geo) => (
                <Geography key={geo.rsmKey} geography={geo} style={{
                  hover: { fill: "#adadad" },
                  pressed: { fill: "#5a5a5a" },
                }} />
              ))
            }
          </Geographies>
          {/* Display the location coordinates of our location with a red circle. */}
          {location && location.latitude && location.longitude && (
            <Marker coordinates={[location.longitude, location.latitude]}>
              <circle r={5} fill="#F53" />
            </Marker>
          )}
        </ComposableMap>
        </Box>
      </Box>
    );
  }
  
export default Geolocate;