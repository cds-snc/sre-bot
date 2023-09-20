import {
  Box,
  Button,
  CircularProgress,
  TextField,
  Grid,
  Typography,
} from "@mui/material";
// import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import { useState } from "react";

interface GeolocateResponse {
  country: string | null;
  city: string | null;
  latitude: number | null;
  longitude: number | null;
}

export const Geolocate: React.FC = () => {
  const [ip, setIp] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [data, setData] = useState<GeolocateResponse | null>(null);
  // const [viewport, setViewport] = useState({
  //   latitude: 0,
  //   longitude: 0,
  //   zoom: 1,
  //   width: "100%",
  //   height: "50vh"
  // });
  // const [selectedLocation, setSelectedLocation] = useState<GeolocateResponse | null>(null);

  const handleButtonClick = async () => {
    setIsLoading(true);
    const response = await fetch(
      `https://sre-bot.cdssandbox.xyz/geolocate/${ip}`
    );
    const data = await response.json();
    setData(data);
    // setViewport({
    //   latitude: data.latitude || 0,
    //   longitude: data.longitude || 0,
    //   zoom: 13,
    //   width: "100%",
    //   height: "50vh"
    // });
    setIsLoading(false);
  };

  return (
    <Box>
      <Box bgcolor="primary.main" py={2}>
        <Typography variant="h2" align="center" color="textPrimary">
          Geolocate
        </Typography>
      </Box>
      <Box py={4}>
        <Typography variant="body1" align="center" color="textSecondary">
          Enter an IP address to get its geolocation data.
        </Typography>
      </Box>
      <Box p={4}>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <TextField
              label="IP Address"
              variant="outlined"
              value={ip}
              onChange={(event) => setIp(event.target.value)}
              fullWidth
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <Button
              variant="contained"
              color="primary"
              onClick={handleButtonClick}
              disabled={isLoading}
              fullWidth
            >
              {isLoading ? <CircularProgress size={24} /> : "Geolocate"}
            </Button>
          </Grid>
        </Grid>
      </Box>
      {data && (
        <Box p={4}>
          <Typography variant="body1" align="center" color="textSecondary">
            {`Location: ${data.city}, ${data.country} (${data.latitude}, ${data.longitude})`}
          </Typography>
          <Typography variant="body1" align="center" color="textSecondary">
            Map
          </Typography>
        </Box>
      )}
    </Box>
  );
};
