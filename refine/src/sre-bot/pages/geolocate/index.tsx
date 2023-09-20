import { Box, Button, CircularProgress, TextField } from "@mui/material";
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

  const handleButtonClick = async () => {
    setIsLoading(true);
    const response = await fetch(
      `https://sre-bot.cdssandbox.xyz/geolocate/${ip}`
    );
    const json = await response.json();
    setData(json);
    setIsLoading(false);
  };

  return (
    <Box display="flex" flexDirection="column" alignItems="center">
      <TextField
        label="IP Address"
        variant="outlined"
        value={ip}
        onChange={(event) => setIp(event.target.value)}
        style={{ marginBottom: "1rem" }}
      />
      <Button
        variant="contained"
        color="primary"
        onClick={handleButtonClick}
        disabled={isLoading}
        style={{ marginBottom: "1rem" }}
      >
        {isLoading ? <CircularProgress size={24} /> : "Geolocate"}
      </Button>
      {data && (
        <Box>
          <p>City: {data.city}</p>
          <p>Country: {data.country}</p>
          <p>Latitude: {data.latitude}</p>
          <p>Longitude: {data.longitude}</p>
        </Box>
      )}
    </Box>
  );
};
